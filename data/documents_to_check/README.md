# documents_to_check/

Sample real-world privacy policies, collected to test the compliance checker against actual
documents rather than synthetic ones. Each file is the exact wording from the source (fetched
directly, not summarized/paraphrased by an AI), lightly cleaned to remove page navigation,
scripts, and styling.

| File | Company | Type | Source | Fetched |
|---|---|---|---|---|
| `github_privacy_policy.md` | GitHub (big tech) | General Privacy Statement | [docs.github.com](https://docs.github.com/en/site-policy/privacy-policies/github-privacy-statement) (mirrored from the public [github/site-policy](https://github.com/github/site-policy/blob/main/Policies/privacy-policies/github-general-privacy-statement.md) repo) | 2026-07-04 |
| `teladoc_privacy_policy.md` | Teladoc Health (healthcare/telehealth) | General Privacy Policy | [teladochealth.com/privacy-policy](https://www.teladochealth.com/privacy-policy) | 2026-07-04 |
| `ebay_privacy_policy.md` | eBay (e-commerce) | User Privacy Notice | [ebay.com/help/policies/...](https://www.ebay.com/help/policies/member-behaviour-policies/user-privacy-notice-privacy-policy?id=4260) | 2026-07-04 |
| `mozilla_privacy_policy.md` | Mozilla (tech, bonus 4th sample) | Websites, Communications & Cookies Privacy Notice | [mozilla.org/en-US/privacy/websites](https://www.mozilla.org/en-US/privacy/websites/) | 2026-07-04 |

## Why these four

- **GitHub** and **Mozilla** give two "big tech" style policies, both explicitly using
  GDPR-style language (Data Controller / Data Processor).
- **Teladoc Health** is a healthcare/telehealth company, and its policy explicitly discusses
  PHI (Protected Health Information) and HIPAA — directly relevant for testing HIPAA gap checks.
- **eBay** gives an e-commerce example, including region-specific data controller entities and
  state-level (e.g. California) privacy disclosures.

## How these were fetched

Each was downloaded as raw HTML (or, for GitHub, the underlying markdown source from its public
policy repo) and converted to clean text by mechanically stripping tags/scripts/styles — not by
passing the page through an AI summarizer. This matters for a project whose whole point is
citing *exact* wording, since an AI-paraphrased copy would not reliably match the real document.
