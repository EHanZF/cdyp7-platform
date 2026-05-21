export type AuthorityClass = "non_authoritative" | "authoritative";

export type ALMItem = {
  id: number | string;
  name: string;
  tracker?: string;
  typeName?: string;
  status?: string;
  priority?: string;
  assignedTo: string[];
  storyPoints?: number;
  createdAt?: string;
  modifiedAt?: string;
  versions: string[];
  subjects: string[];
  children: string[];
  deliveryName?: string;
  deliveryDate?: string;
  dueDate?: string;
  remaining?: number;
  blocked?: boolean;
  url?: string;
  customFields: Record<string, unknown>;
};

export type DeliverySummary = {
  id: string;
  name: string;
  deliveryDate?: string;
  totalItems: number;
  completedItems: number;
  remainingItems: number;
};

export type ALMDashboardState = {
  generatedAt: string;
  source: "codebeamer" | "codebeamer-demo";
  authority: AuthorityClass;
  receiptBacked: boolean;
  receiptId?: string;
  query?: string;
  totals: {
    items: number;
    open: number;
    inProgress: number;
    closed: number;
    highPriority: number;
  };
  byStatus: Record<string, number>;
  byPriority: Record<string, number>;
  byTracker: Record<string, number>;
  deliveries?: DeliverySummary[];
  items: ALMItem[];
};
