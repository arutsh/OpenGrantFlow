import {
  SITE_SECTION_STATUSES,
  readFrontmatterFile,
  type SiteSectionStatus,
} from "./siteContent";
import rawNotice from "../content/notices/privacy-banner.md?raw";

export interface PrivacyNotice {
  status: SiteSectionStatus;
  version: string;
  body: string;
}

export function buildPrivacyNotice(raw: string, path: string): PrivacyNotice {
  const { data, body } = readFrontmatterFile(raw, path);

  const errors: string[] = [];
  if (data.status === undefined) {
    errors.push(`${path}: missing required field "status"`);
  } else if (!SITE_SECTION_STATUSES.includes(data.status as SiteSectionStatus)) {
    errors.push(`${path}: invalid "status" value "${String(data.status)}"`);
  }
  // Dismissal is stored and compared as a string, so a bare YAML number is rejected.
  if (data.version === undefined) {
    errors.push(`${path}: missing required field "version"`);
  } else if (typeof data.version !== "string" || !data.version.trim()) {
    errors.push(`${path}: "version" must be a non-empty string`);
  }
  if (!body) {
    errors.push(`${path}: body must not be empty`);
  }
  if (errors.length > 0) {
    throw new Error(`Privacy notice validation failed:\n${errors.join("\n")}`);
  }
  return {
    status: data.status as SiteSectionStatus,
    version: data.version as string,
    body,
  };
}

export const privacyNotice = buildPrivacyNotice(
  rawNotice,
  "content/notices/privacy-banner.md",
);
