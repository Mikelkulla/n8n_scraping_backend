import { apiRequest } from "./httpClient";
import type {
  BusinessTypeEmailRuleResponse,
  BusinessTypeEmailRulesResponse,
  EmailSettingsResponse,
  UpdateBusinessTypeEmailRuleRequest,
  UpdateEmailSettingsRequest,
} from "./types";

export function getEmailSettings() {
  return apiRequest<EmailSettingsResponse>("/email-settings");
}

export function updateEmailSettings(payload: UpdateEmailSettingsRequest) {
  return apiRequest<EmailSettingsResponse>("/email-settings", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function listBusinessTypeEmailRules() {
  return apiRequest<BusinessTypeEmailRulesResponse>("/email-settings/business-types");
}

export function updateBusinessTypeEmailRule(businessType: string, payload: UpdateBusinessTypeEmailRuleRequest) {
  return apiRequest<BusinessTypeEmailRuleResponse>(
    `/email-settings/business-types/${encodeURIComponent(businessType)}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
  );
}
