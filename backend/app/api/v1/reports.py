"""On-demand portfolio reports.

No background worker: performance/allocation are cheap, deterministic
computations already used live by /performance and /allocation, so
"queued"/"running" would be theater rather than a real async job. Report
*content* is never persisted — it's regenerated fresh from current data on
every download, so a downloaded report is never a stale snapshot.

The download endpoint is hit from a plain `<a href>` in the browser, which
can't carry an Authorization header, so it's protected by an HMAC-signed
token minted at generate time instead of Bearer auth.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_owned_portfolio, parse_user_uuid
from app.api.v1.portfolios import get_allocation, get_performance, _to_holding_response
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.rate_limit import rate_limit_dependency
from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.holding import Holding
from app.models.portfolio import Portfolio
from app.models.report_job import ReportJob
from app.schemas.report import ReportJobResponse, ReportSummaryResponse

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(rate_limit_dependency)])


def _sign(job_id: UUID) -> str:
    secret = get_settings().APP_SECRET_KEY.encode()
    return hmac.new(secret, str(job_id).encode(), hashlib.sha256).hexdigest()[:32]


def _download_url(request: Request, job: ReportJob) -> str | None:
    if job.status != "ready":
        return None
    token = _sign(job.id)
    return str(request.url_for("download_report", job_id=job.id)) + f"?token={token}"


@router.post("/{id}/generate", response_model=ReportJobResponse, status_code=201)
async def generate_report(
    request: Request,
    portfolio: Portfolio = Depends(get_owned_portfolio),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ReportJobResponse:
    job = ReportJob(portfolio_id=portfolio.id, user_id=parse_user_uuid(user_id), status="ready")
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return ReportJobResponse(
        job_id=job.id, status=job.status, created_at=job.created_at, download_url=_download_url(request, job)
    )


@router.get("/{id}/summary", response_model=ReportSummaryResponse)
async def get_report_summary(
    portfolio: Portfolio = Depends(get_owned_portfolio),
    db: AsyncSession = Depends(get_db),
) -> ReportSummaryResponse:
    performance = await get_performance(portfolio=portfolio, db=db, range="ALL")
    allocation = await get_allocation(portfolio=portfolio, db=db)
    return ReportSummaryResponse(
        portfolio_id=portfolio.id,
        generated_at=datetime.now(timezone.utc),
        performance=performance,
        allocation=allocation,
    )


@router.get("/jobs/{job_id}", response_model=ReportJobResponse)
async def get_report_job(
    request: Request,
    job_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ReportJobResponse:
    result = await db.execute(
        select(ReportJob).where(ReportJob.id == job_id, ReportJob.user_id == parse_user_uuid(user_id))
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise AppError(code="REPORT_JOB_NOT_FOUND", message="Report job not found.", status_code=404)
    return ReportJobResponse(
        job_id=job.id, status=job.status, created_at=job.created_at, download_url=_download_url(request, job)
    )


def _fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.2f}%"


def _fmt_ratio(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def _fmt_money(value: float, currency: str) -> str:
    return f"{currency} {value:,.2f}"


@router.get("/jobs/{job_id}/download", name="download_report", response_class=HTMLResponse)
async def download_report(job_id: UUID, token: str, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    result = await db.execute(select(ReportJob).where(ReportJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None or job.status != "ready":
        raise AppError(code="REPORT_JOB_NOT_FOUND", message="Report job not found.", status_code=404)
    if not hmac.compare_digest(token, _sign(job.id)):
        raise AppError(code="INVALID_TOKEN", message="Invalid or expired download link.", status_code=403)

    portfolio_result = await db.execute(select(Portfolio).where(Portfolio.id == job.portfolio_id))
    portfolio = portfolio_result.scalar_one_or_none()
    if portfolio is None:
        raise AppError(code="PORTFOLIO_NOT_FOUND", message="Portfolio not found.", status_code=404)

    performance = await get_performance(portfolio=portfolio, db=db, range="ALL")
    allocation = await get_allocation(portfolio=portfolio, db=db)
    holdings_result = await db.execute(select(Holding).where(Holding.portfolio_id == portfolio.id).order_by(Holding.symbol))
    holdings = [_to_holding_response(h) for h in holdings_result.scalars().all()]

    currency = portfolio.base_currency
    generated_at = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    asset_class_rows = "".join(
        f"<tr><td>{label}</td><td>{_fmt_money(value, currency)}</td>"
        f"<td>{allocation.by_asset_class.percentage.get(label, 0):.1f}%</td></tr>"
        for label, value in allocation.by_asset_class.market_value.items()
    )
    holding_rows = "".join(
        f"<tr><td>{h.symbol}</td><td>{h.exchange}</td><td>{h.asset_class or '—'}</td>"
        f"<td>{h.quantity:g}</td><td>{_fmt_money(h.avg_price, currency)}</td>"
        f"<td>{_fmt_money(h.current_price, currency) if h.current_price is not None else '—'}</td>"
        f"<td>{_fmt_money(h.market_value, currency)}</td>"
        f"<td class=\"{'gain' if h.unrealized_pnl >= 0 else 'loss'}\">"
        f"{_fmt_money(h.unrealized_pnl, currency)} ({h.unrealized_pnl_percent:+.2f}%)</td></tr>"
        for h in holdings
    )

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{portfolio.name} — FINMIND report</title>
<style>
body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; background: #161826; color: #e9e9ed; padding: 40px; max-width: 860px; margin: 0 auto; }}
h1 {{ font-size: 22px; font-weight: 500; margin-bottom: 4px; }}
.meta {{ color: #9397ab; font-size: 13px; margin-bottom: 32px; }}
h2 {{ font-size: 15px; font-weight: 500; margin: 32px 0 12px; color: #b5abfc; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #ffffff1a; }}
th {{ color: #9397ab; font-weight: 500; text-transform: uppercase; font-size: 11px; letter-spacing: 0.05em; }}
.stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }}
.stat {{ background: #232532; border-radius: 8px; padding: 12px 16px; }}
.stat .label {{ font-size: 11px; color: #9397ab; text-transform: uppercase; }}
.stat .value {{ font-size: 20px; margin-top: 4px; }}
.gain {{ color: #3fbf8a; }}
.loss {{ color: #e26a63; }}
</style></head>
<body>
<h1>{portfolio.name}</h1>
<div class="meta">{currency} portfolio &middot; generated {generated_at} by FINMIND</div>

<h2>Performance</h2>
<div class="stats">
  <div class="stat"><div class="label">Total return</div><div class="value">{_fmt_pct(performance.simple_return)}</div></div>
  <div class="stat"><div class="label">CAGR</div><div class="value">{_fmt_pct(performance.cagr)}</div></div>
  <div class="stat"><div class="label">Sharpe ratio</div><div class="value">{_fmt_ratio(performance.sharpe_ratio)}</div></div>
  <div class="stat"><div class="label">Max drawdown</div><div class="value">{_fmt_pct(performance.max_drawdown)}</div></div>
</div>

<h2>Allocation by asset class</h2>
<table><thead><tr><th>Asset class</th><th>Market value</th><th>Weight</th></tr></thead>
<tbody>{asset_class_rows}</tbody></table>

<h2>Holdings ({len(holdings)})</h2>
<table><thead><tr><th>Symbol</th><th>Exchange</th><th>Class</th><th>Qty</th><th>Avg</th><th>Last</th><th>Market value</th><th>Unrealised P/L</th></tr></thead>
<tbody>{holding_rows}</tbody></table>
</body></html>"""

    return HTMLResponse(
        content=html,
        headers={"Content-Disposition": f'attachment; filename="{portfolio.name.replace(" ", "-")}-report.html"'},
    )
