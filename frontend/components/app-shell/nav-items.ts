import {
  Bot,
  Building2,
  LayoutDashboard,
  Wallet,
  FileSearch,
  ClipboardCheck,
  FileText,
  Settings,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/portfolio", label: "Portfolio", icon: Wallet },
  { href: "/research", label: "Research", icon: FileSearch },
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/brokers", label: "Brokers", icon: Building2 },
  { href: "/trade-approvals", label: "Trade Approvals", icon: ClipboardCheck },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
];
