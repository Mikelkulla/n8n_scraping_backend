import { useQuery } from "@tanstack/react-query";
import { downloadLeadsCsv, exportLeadsJson, listLeads } from "../api";
import type { ListLeadsParams } from "../api";
import { queryKeys } from "./queryKeys";

export function useLeads(params: ListLeadsParams = {}) {
  return useQuery({
    queryKey: queryKeys.leads(params),
    queryFn: () => listLeads(params),
  });
}

export function useExportLeadsJson() {
  return useQuery({
    queryKey: queryKeys.exportLeads,
    queryFn: exportLeadsJson,
  });
}

export async function downloadExportedLeads(filename = "leads_export.csv") {
  const blob = await downloadLeadsCsv();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
