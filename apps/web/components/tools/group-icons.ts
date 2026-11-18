import type { ToolDescriptor } from "@autobots/api-client";
import {
  Calculator,
  CalendarClock,
  ChartLine,
  Code,
  Compass,
  Globe,
  FileText,
  GraduationCap,
  Link2,
  ListTodo,
  type LucideIcon,
  Network,
  Plug,
  Search,
  Users,
} from "lucide-react";

// Decorative: the group heading and the tool's title carry the meaning.
export const GROUP_ICONS: Readonly<
  Record<ToolDescriptor["group"], LucideIcon>
> = {
  planning: ListTodo,
  general: Calculator,
  web_search: Search,
  web_extraction: Link2,
  web_crawling: Network,
  files: FileText,
  market_data: ChartLine,
  browsing: Compass,
  code: Code,
  connectors: Plug,
  delegation: Users,
  learning: GraduationCap,
  automation: CalendarClock,
  google: Globe,
};
