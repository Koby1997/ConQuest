import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { api } from "../api";
import { CATEGORY_ICONS, colorFor, SIZE_LABELS } from "../categories";
import { relativeDay } from "../format";
import type { DiscoveryRun, Meta, Settings } from "../types";

interface Props {
  meta: Meta;
  onSaved: () => void;
}

const TIERS = ["local", "regional", "major"] as const;

export function SettingsView({ meta, onSaved }: Props) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [runs, setRuns] = useState<DiscoveryRun[]>([]);
  const [homeLabel, setHomeLabel] = useState("");
  const [hours, setHours] = useState<Record<string, string>>({});
  const [profile, setProfile] = useState("");
  const [boosts, setBoosts] = useState<Record<string, number>>({});
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [profileChanged, setProfileChanged] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = (s: Settings) => {
    setSettings(s);
    setHomeLabel(s.home_label);
    setHours(Object.fromEntries(TIERS.map((t) => [t, String((s.drive_limits[t] ?? 0) / 60)])));
    setProfile(s.interest_profile);
    setBoosts({ ...s.category_boosts });
  };

  useEffect(() => {
    api.settings().then(load).catch((e: Error) => setMessage({ kind: "error", text: e.message }));
    api.runs().then(setRuns).catch(() => setRuns([]));
  }, []);

  if (!settings) {
    return <div className="view">{message ? <p className="error">{message.text}</p> : <p className="muted">Loading…</p>}</div>;
  }

  const save = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const limits: Record<string, number> = {};
      for (const tier of TIERS) {
        const value = Number(hours[tier]);
        if (!Number.isFinite(value) || value <= 0) throw new Error(`Enter a drive limit in hours for ${tier} events.`);
        limits[tier] = Math.round(value * 60);
      }
      const changedProfile = profile.trim() !== settings.interest_profile.trim();
      const saved = await api.saveSettings({
        home_label: homeLabel.trim() !== settings.home_label ? homeLabel.trim() : undefined,
        drive_limits: limits,
        interest_profile: profile,
        category_boosts: boosts,
      });
      load(saved);
      if (changedProfile) setProfileChanged(true);
      setMessage({ kind: "ok", text: "Saved." });
      onSaved();
    } catch (e) {
      setMessage({ kind: "error", text: (e as Error).message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="view settings">
      <section className="panel">
        <h2>🔎 Finding new events</h2>
        <p>
          ConQuest doesn't search the web by itself. The research is done by Claude Code on your Claude plan, then saved
          here. In the Claude Code panel for this project, type:
        </p>
        <ul className="commands">
          <li>
            <code>/discover</code>: the next few categories in the rotation (good once a week)
          </li>
          <li>
            <code>/discover maker</code> (or <code>space</code>, <code>comic</code>, <code>film</code>…): one category
          </li>
          <li>
            <code>/discover refresh</code>: check for newly announced dates on events you already have
          </li>
          <li>
            <code>/discover rescore</code>: re-score everything after you change your interests below
          </li>
        </ul>
      </section>

      <section className="panel">
        <h2>🏠 Home</h2>
        <label className="field">
          Starting point for drive times
          <input value={homeLabel} onChange={(e) => setHomeLabel(e.target.value)} placeholder="City, ST" />
        </label>
        <p className="muted small">
          Currently {settings.home_lat.toFixed(3)}, {settings.home_lng.toFixed(3)}. Drive times are estimates from
          straight-line distance.
        </p>

        <h3>How far you'll drive</h3>
        <div className="tiers">
          {TIERS.map((tier) => (
            <label key={tier} className="field">
              <span>
                <strong className="tier-name">{SIZE_LABELS[tier]} events</strong>
                <br />
                <span className="small">{meta.size_tiers[tier].replace(/^\w+ \((.*)\)$/, "$1")}</span>
              </span>
              <span className="hours">
                <input
                  type="number"
                  min={0.5}
                  step={0.5}
                  value={hours[tier] ?? ""}
                  onChange={(e) => setHours({ ...hours, [tier]: e.target.value })}
                />
                hours
              </span>
            </label>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>❤️ What you're into</h2>
        <label className="field">
          <span>
            In your own words. <code>/discover</code> scores every event against this.
          </span>
          <textarea value={profile} onChange={(e) => setProfile(e.target.value)} rows={7} />
        </label>
        {profileChanged && (
          <p className="hint">
            Interests updated. Run <code>/discover rescore</code> in Claude Code to re-score existing events.
          </p>
        )}

        <h3>Category boosts</h3>
        <p className="muted small">
          Nudge whole categories up or down. Your 👍/👎 also teach categories automatically (shown as "learned").
        </p>
        <div className="boosts">
          {Object.entries(meta.categories).map(([slug, label]) => {
            const learned = settings.learned_category_points[slug];
            return (
              <div key={slug} className="boost" style={{ "--chip": colorFor(slug) } as CSSProperties}>
                <span className="boost__label">
                  {CATEGORY_ICONS[slug]} {label}
                </span>
                <select
                  value={boosts[slug] ?? 0}
                  onChange={(e) => setBoosts({ ...boosts, [slug]: Number(e.target.value) })}
                >
                  <option value={-2}>Much less</option>
                  <option value={-1}>Less</option>
                  <option value={0}>Normal</option>
                  <option value={1}>More</option>
                  <option value={2}>Much more</option>
                </select>
                {learned ? (
                  <span className={`learned ${learned > 0 ? "learned--up" : "learned--down"}`}>
                    learned {learned > 0 ? "+" : ""}
                    {learned}
                  </span>
                ) : (
                  <span className="learned" />
                )}
              </div>
            );
          })}
        </div>
      </section>

      <div className="save-bar">
        <button className="button button--primary" onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save settings"}
        </button>
        {message && <span className={message.kind === "ok" ? "ok" : "error"}>{message.text}</span>}
      </div>

      <section className="panel">
        <h2>📜 Discovery log</h2>
        {runs.length === 0 ? (
          <p className="muted">No searches yet. Run /discover seed in Claude Code to get started.</p>
        ) : (
          <table className="runs">
            <thead>
              <tr>
                <th>When</th>
                <th>Mode</th>
                <th>Searched</th>
                <th>New</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} title={run.notes ?? ""}>
                  <td>{relativeDay(run.created_at)}</td>
                  <td>{run.mode}</td>
                  <td>
                    {run.categories.map((c) => meta.categories[c] ?? c).join(", ") || "-"}
                    {run.regions.length > 0 && <span className="muted"> · {run.regions.join(", ")}</span>}
                  </td>
                  <td>{run.new_series}</td>
                  <td>{run.updated_series}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
