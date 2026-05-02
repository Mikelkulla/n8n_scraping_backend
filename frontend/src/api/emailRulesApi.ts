import { apiRequest } from "./httpClient";
import type {
  ApplyEmailCategoryRulesResponse,
  EmailCategoryRuleResponse,
  ListEmailCategoryRulesResponse,
  UnknownEmailLocalPartsResponse,
  UpdateEmailCategoryRuleRequest,
} from "./types";

export function listEmailCategoryRules() {
  return apiRequest<ListEmailCategoryRulesResponse>("/email-category-rules");
}

export function updateEmailCategoryRule(pattern: string, payload: UpdateEmailCategoryRuleRequest) {
  return apiRequest<EmailCategoryRuleResponse>(
    `/email-category-rules/${encodeURIComponent(pattern)}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
  );
}

export function listUnknownEmailLocalParts() {
  return apiRequest<UnknownEmailLocalPartsResponse>("/lead-emails/unknown");
}

export function applyEmailCategoryRules() {
  return apiRequest<ApplyEmailCategoryRulesResponse>("/email-category-rules/apply", {
    method: "POST",
  });
}
