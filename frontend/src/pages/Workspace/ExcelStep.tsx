import { api } from "../../api/client";
import { Check, Download, FileSpreadsheet } from "../../components/icons";
import { Status, Step, useCountUp } from "../../components/ui";
import { fmtSize, nf } from "../../lib/format";
import type { Comparison } from "../../types/api";

/**
 * Comparison result and the final workbook. MATCH / MISMATCH / REVIEW REQUIRED are the only verdicts; rows where
 * no source holds a value are shown apart, as "not compared", and never counted as a verdict.
 */
export function ExcelStep({
  cmp,
  downloaded,
  onDownload,
}: {
  cmp: Comparison;
  downloaded: boolean;
  onDownload: () => void;
}) {
  const t = useCountUp();
  const cf = (n: number) => nf(Math.round(n * t));
  const tags = cmp.scope_tag_count;
  const match = cmp.totals.MATCH ?? 0;
  const mismatch = cmp.totals.MISMATCH ?? 0;
  const review = cmp.totals["REVIEW REQUIRED"] ?? 0;
  const pct = (n: number) => (tags ? (n / tags) * 100 * t : 0);

  const verdicts = [
    { label: "MATCH", n: match, tone: "match" },
    { label: "MISMATCH", n: mismatch, tone: "mismatch" },
    { label: "REVIEW REQUIRED", n: review, tone: "review" },
  ];

  const status = downloaded ? <Status tone="match" kind="done">Downloaded</Status> : <Status tone="accent">Ready to download</Status>;

  return (
    <Step id="st-out" title="Excel" status={status} last onBlue>
      <div className="mt-panel mt-step-content mt-result">
        <div className="mt-totals">
          <span className="mt-total">
            <span className="mt-total-n">{cf(tags)}</span>tags
          </span>
          <span className="mt-total">
            <span className="mt-total-n">{cf(tags * cmp.attributes.length)}</span>attribute checks
          </span>
        </div>

        <div className="mt-verdict-wrap">
          <div className="mt-verdicts">
            <span className="mt-overline mt-overline-row">
              <span>VERDICTS</span>
              <span className="mt-overline-plain">{cf(match + mismatch + review)} compared</span>
            </span>
            <div className="mt-verdict-grid">
              {verdicts.map((v) => (
                <div key={v.label} className={`mt-verdict is-${v.tone}`}>
                  <span className="mt-verdict-n">{cf(v.n)}</span>
                  <span className="mt-verdict-label">{v.label}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="mt-notcompared">
            <span className="mt-overline">NOT COMPARED</span>
            <div className="mt-verdict is-nosource">
              <span className="mt-verdict-n">{cf(cmp.no_source_value)}</span>
              <span className="mt-verdict-label">NO SOURCE VALUE</span>
            </div>
          </div>
        </div>

        <div className="mt-attr-table">
          <div className="mt-attr-grid mt-attr-head">
            <span>Attribute</span>
            <span />
            <span className="tone-match">Match</span>
            <span className="tone-mismatch">Mism.</span>
            <span className="tone-review">Review</span>
            <span>No src</span>
          </div>
          {cmp.attributes.map((a) => (
            <div key={a.code} className="mt-attr-grid mt-attr-rowline">
              <span className="mono mt-attr-name">{a.label}</span>
              <span className="mt-stackbar" aria-hidden="true">
                <span className="is-match" style={{ width: `${pct(a.counts.MATCH ?? 0)}%` }} />
                <span className="is-mismatch" style={{ width: `${pct(a.counts.MISMATCH ?? 0)}%` }} />
                <span className="is-review" style={{ width: `${pct(a.counts["REVIEW REQUIRED"] ?? 0)}%` }} />
                <span className="mt-stackbar-gap" />
                <span className="is-nosource" style={{ width: `max(0px, calc(${pct(a.no_source_value)}% - 3px))` }} />
              </span>
              <span className="mono">{cf(a.counts.MATCH ?? 0)}</span>
              <span className="mono">{cf(a.counts.MISMATCH ?? 0)}</span>
              <span className="mono">{cf(a.counts["REVIEW REQUIRED"] ?? 0)}</span>
              <span className="mono mt-ink-3">{cf(a.no_source_value)}</span>
            </div>
          ))}
        </div>

        {cmp.output && (
          <div className="mt-final">
            <div className="mt-final-text">
              <FileSpreadsheet size={20} className="tone-accent mt-final-icon" />
              <div className="mt-col mt-gap-2">
                <span className="mt-done-label">Comparison workbook ready</span>
                <span className="mono mt-final-file">
                  {cmp.output.file_name} · {fmtSize(cmp.output.file_size)}
                </span>
              </div>
            </div>
            <a
              className={`btn btn-final${downloaded ? " is-done" : ""}`}
              href={api.downloadUrl(cmp.run_id, cmp.output.id)}
              download
              onClick={onDownload}
            >
              {downloaded ? <Check className="pop" /> : <Download />}
              {downloaded ? "Downloaded · download again" : "Download comparison Excel"}
            </a>
          </div>
        )}
      </div>
    </Step>
  );
}
