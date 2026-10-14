"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { uploadPdf } from "@/lib/api";
import "@/styles/landing.css";

/* ------------------------------------------------------------------ *
 * Interactive "Fit to one page" demo — mirrors the vanilla JS in the
 * original static page. Shows the LaTeX source with highlighted edits
 * and a live one/two page pill toggle.
 * ------------------------------------------------------------------ */

const B1L =
  "Cut orders API p95 latency from 840 ms to 210 ms by adding read-through caching, removing N+1 queries, and tuning connection pooling across all services.";
const B1S =
  "Cut orders API p95 latency from 840 ms to 210 ms with read-through caching and N+1 query fixes.";
const B2L =
  "Led migration of 140 services to Kubernetes with zero-downtime cutovers and replaced noisy alerts with SLO burn-rate alerts.";
const B2S = "Led migration of 140 services to Kubernetes with zero-downtime cutovers.";
const B3 = "Mentored four engineers and ran weekly design reviews.";

interface Line {
  text: string;
  changed: boolean;
}

function sourceLines(fit: boolean): Line[] {
  const a: Line[] = [
    { text: String.raw`\section{Experience}`, changed: false },
    { text: String.raw`\resumeSubheading`, changed: false },
    { text: String.raw`  {Senior Software Engineer}{2022 -- Present}`, changed: false },
    { text: String.raw`  {Acme Cloud}{Remote}`, changed: false },
    { text: String.raw`\resumeItemListStart`, changed: false },
    { text: String.raw`  \resumeItem{` + (fit ? B1S : B1L) + `}`, changed: fit },
    { text: String.raw`  \resumeItem{` + (fit ? B2S : B2L) + `}`, changed: fit },
    { text: String.raw`  \resumeItem{` + B3 + `}`, changed: false },
    { text: String.raw`\resumeItemListEnd`, changed: false },
  ];
  if (fit) a.push({ text: String.raw`\vspace{-6pt}`, changed: true });
  a.push({ text: String.raw`\section{Education}`, changed: false });
  a.push({ text: String.raw`% ... Education, then \section{Skills}`, changed: false });
  return a;
}

/** Split a raw latex line into styled React nodes (commands + braces). */
function LaTeXLine({ text }: { text: string }) {
  if (text.startsWith("%")) {
    return <span className="br">{text}</span>;
  }
  // Highlight LaTeX commands and braces.
  const parts = text.split(/(\\[a-zA-Z]+|[{}])/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("\\")) return <span key={i} className="cmd">{part}</span>;
        if (part === "{" || part === "}") return <span key={i} className="br">{part}</span>;
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}

function StudioMock() {
  const [fit, setFit] = useState(false);
  const [highlight, setHighlight] = useState(false);
  const touched = useRef(false);
  const hlTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const t = setTimeout(() => {
      if (!touched.current) setFit(true);
    }, 2600);
    return () => clearTimeout(t);
  }, []);

  const toggle = useCallback(() => {
    touched.current = true;
    setFit((f) => !f);
    setHighlight(true);
    clearTimeout(hlTimer.current);
    hlTimer.current = window.setTimeout(() => setHighlight(false), 1600);
  }, []);

  const lines = sourceLines(fit);
  const p1 = fit ? B1S : B1L;
  const p2 = fit ? B2S : B2L;

  return (
    <div className="studio" aria-label="Example of the Betterleaf editor fitting a resume onto one page">
      <div className="s-bar">
        <span className="s-tab">resume.tex</span>
        <span className="s-right">
          <span className={`pill${fit ? " ok" : ""}`}>{fit ? "1 page" : "2 pages"}</span>
          <span className="fake-btn" aria-hidden="true">PDF</span>
          <span className="fake-btn" aria-hidden="true">.tex</span>
        </span>
      </div>
      <div className="s-body">
        <div className="left">
          <div className="code" aria-label="LaTeX source">
            {lines.map((line, i) => (
              <div key={i} className={`ln${line.changed ? " chg" : ""}`}>
                <span className="no">{i + 1}</span>
                <span className="tx">
                  <LaTeXLine text={line.text} />
                </span>
              </div>
            ))}
          </div>
          <div className="ai">
            <p>
              {fit ? (
                <><b>Shortened two bullets and tightened spacing.</b> Compiled: 1 page.</>
              ) : (
                <><b>Compiled: 2 pages.</b> The Skills section spills onto page 2.</>
              )}
            </p>
            <button className="btn" type="button" onClick={toggle}>
              {fit ? "Undo" : "Fit to one page"}
            </button>
          </div>
        </div>
        <div className="right">
          <div className={`paper${fit ? "" : " spill"}`} aria-label="Live PDF preview">
            <div className="nm">Alex Rivera</div>
            <div className="ct">alex@rivera.dev &nbsp;|&nbsp; github.com/arivera &nbsp;|&nbsp; Berlin</div>
            <h4>Experience</h4>
            <div className="rw"><b>Senior Software Engineer</b><span>2022 – Present</span></div>
            <div className="rw"><i>Acme Cloud</i><i>Remote</i></div>
            <ul>
              <li className={highlight && fit ? "hl" : ""}>{p1}</li>
              <li className={highlight && fit ? "hl" : ""}>{p2}</li>
              <li>{B3}</li>
            </ul>
            <h4>Education</h4>
            <div className="rw"><b>B.Sc. Computer Science, TU Munich</b><span>2018</span></div>
            <div className="pb"><span>Page 2 starts here</span></div>
            <div className="p2">
              <h4>Skills</h4>
              <div><b>Languages:</b> Go, Python, TypeScript, SQL</div>
              <div><b>Tools:</b> Kubernetes, PostgreSQL, Terraform</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const Check = ({ stroke = "#2e7d5b" }: { stroke?: string }) => (
  <svg viewBox="0 0 20 20" fill="none" stroke={stroke} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M4 10.5l4 4 8-9" />
  </svg>
);

const Leaf = () => (
  <svg className="f-leaf" viewBox="-3 0 27 36" aria-hidden="true">
    <path d="M9 33.5V13" stroke="currentColor" strokeWidth="4.6" strokeLinecap="round" fill="none" />
    <path d="M9 14C8.5 6 14.5 1 23 1.2 23.2 9.5 17.5 15 9 14Z" fill="#2e7d5b" />
    <path d="M9.6 13.4L20.5 3.4" stroke="#f2f4f0" strokeWidth="1.2" strokeLinecap="round" fill="none" />
    <path d="M9 21.5C11 17.8 15.5 17.2 19.8 18.2 18.8 22 14 23.6 9 21.5Z" fill="#2e7d5b" />
    <path d="M9 21.5C7 17.8 2.5 17.2-1.8 18.2-.8 22 4 23.6 9 21.5Z" fill="#2e7d5b" />
  </svg>
);

/** Landing page for guests with no workspace. */
export function LandingPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<number | undefined>(undefined);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 4200);
  }, []);

  const openPicker = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const onFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      e.target.value = "";
      if (!file) return;
      try {
        await uploadPdf(file);
        router.replace("/workspace");
      } catch {
        showToast("Upload failed. Please try again.");
      }
    },
    [router, showToast],
  );

  const year = new Date().getFullYear();

  return (
    <div className="bl">
      <header className="top">
        <div className="wrap nav">
          <a href="#top" className="logo" aria-label="Betterleaf home">
            <span className="wm">
              Betterlea
              <Leaf />
            </span>
          </a>
          <ul>
            <li><a href="#problems">Why Betterleaf</a></li>
            <li><a href="#how">How it works</a></li>
            <li><a href="#pricing">Pricing</a></li>
            <li><a href="#faq">FAQ</a></li>
          </ul>
          <button className="btn sm" type="button" onClick={openPicker}>
            Upload your resume
          </button>
        </div>
      </header>

      <main id="top">
        {/* HERO */}
        <div className="hero">
          <div className="wrap">
            <div className="hero-top">
              <h1>Stop copy-pasting between ChatGPT and Overleaf.</h1>
              <div>
                <p className="lede">
                  Betterleaf is a LaTeX resume workspace with AI that understands LaTeX. Upload
                  your resume and start editing in 5 seconds. Edit by hand or with AI, preview
                  live, download a clean one-page PDF.
                </p>
                <button className="btn" type="button" onClick={openPicker}>
                  Upload your resume, it&apos;s free
                </button>
                <small>No credit card. Free tier included.</small>
                <p className="who-for">
                  Made for engineers and students who already write their resume in LaTeX.
                </p>
              </div>
            </div>
            <StudioMock />
          </div>
        </div>

        {/* PROBLEMS */}
        <section className="dark" id="problems">
          <div className="wrap">
            <h2>The resume loop you&apos;re tired of, fixed.</h2>
            <div className="pairs">
              <div className="pair">
                <div className="was">
                  <span className="tag">Today</span>
                  <p>ChatGPT in one tab, Overleaf in another, and your resume going back and forth between them.</p>
                </div>
                <div className="now">
                  <span className="tag">In Betterleaf</span>
                  <h3>One workspace for all of it.</h3>
                  <p>Edit, ask the AI, preview and download without leaving the page.</p>
                </div>
              </div>
              <div className="pair">
                <div className="was">
                  <span className="tag">Today</span>
                  <p>ChatGPT gives you LaTeX that sometimes breaks, or a resume that runs onto a second page.</p>
                </div>
                <div className="now">
                  <span className="tag">In Betterleaf</span>
                  <h3>AI that knows LaTeX and the one-page limit.</h3>
                  <p>It works on your actual document and keeps the page count in view.</p>
                </div>
              </div>
              <div className="pair">
                <div className="was">
                  <span className="tag">Today</span>
                  <p>Most AI resume tools charge a lot before you&apos;ve sent a single application.</p>
                </div>
                <div className="now">
                  <span className="tag">In Betterleaf</span>
                  <h3>A free tier for everyone.</h3>
                  <p>Use the full editor for free with limited AI. Pay later only if you want more.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* HOW */}
        <section id="how">
          <div className="wrap">
            <h2 style={{ maxWidth: "16ch" }}>From upload to editing in about 5 seconds.</h2>
            <div className="steps">
              <div className="step">
                <div className="n">1</div>
                <h3>Upload your resume</h3>
                <p>Drop in your current resume as a PDF or Word file. Your workspace opens with it already loaded.</p>
              </div>
              <div className="step">
                <div className="n">2</div>
                <h3>Edit by hand or ask the AI</h3>
                <p>Change the LaTeX directly, or describe the change in plain English. The preview updates as you go.</p>
              </div>
              <div className="step">
                <div className="n">3</div>
                <h3>Download and apply</h3>
                <p>Take away a clean PDF, or the .tex file if you want to keep working elsewhere.</p>
              </div>
            </div>
          </div>
        </section>

        {/* PRICING */}
        <section id="pricing" style={{ background: "var(--paper)", borderTop: "1px solid var(--line)", borderBottom: "1px solid var(--line)" }}>
          <div className="wrap">
            <h2 style={{ maxWidth: "18ch" }}>Free to start. Paid options later.</h2>
            <div className="plans">
              <div className="plan">
                <h3>Free</h3>
                <div className="price">$0</div>
                <p className="sub">For everyone, no card needed.</p>
                <ul>
                  <li><Check />Full editor with live preview</li>
                  <li><Check />Limited AI usage</li>
                  <li><Check />PDF download</li>
                </ul>
                <button className="btn" type="button" onClick={openPicker}>
                  Upload your resume, it&apos;s free
                </button>
              </div>
              <div className="plan soon">
                <h3>Paid</h3>
                <div className="price tba">Details coming soon</div>
                <p className="sub">For when you want more.</p>
                <ul>
                  <li><Check stroke="#8fa398" />More AI usage</li>
                  <li><Check stroke="#8fa398" />Extras we&apos;re still shaping</li>
                </ul>
                <p className="sub">The free tier stays free. We&apos;ll share paid plans before anything is charged.</p>
              </div>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section id="faq">
          <div className="wrap split">
            <div className="head">
              <h2>Questions engineers ask first.</h2>
            </div>
            <div className="faq">
              <details>
                <summary>Do I need to know LaTeX?</summary>
                <p>It helps, because you can edit the source directly. If you&apos;d rather not, describe the change to the AI in plain English and it edits the LaTeX for you.</p>
              </details>
              <details>
                <summary>What can I upload?</summary>
                <p>A PDF or Word version of your current resume. It loads straight into the editor.</p>
              </details>
              <details>
                <summary>What does the free tier include?</summary>
                <p>The full editor, live preview, PDF download and a limited amount of AI usage. No card required.</p>
              </details>
              <details>
                <summary>Can I take my resume with me?</summary>
                <p>Yes. Download a PDF or the .tex file whenever you like.</p>
              </details>
              <details>
                <summary>What happens to my resume?</summary>
                <p>It&apos;s yours. You can download or delete it at any time.</p>
              </details>
            </div>
          </div>
        </section>

        {/* FINAL CTA */}
        <div className="final">
          <div className="wrap">
            <div className="final-box">
              <div>
                <h2>Your resume, ready to edit in 5 seconds.</h2>
                <p>No credit card. Free tier included.</p>
              </div>
              <button className="btn" type="button" onClick={openPicker}>
                Upload your resume, it&apos;s free
              </button>
            </div>
          </div>
        </div>
      </main>

      <footer>
        <div className="wrap">
          <span>© {year} Betterleaf. Built by an engineer who got tired of the copy-paste loop.</span>
          <nav>
            <a href="#">Privacy</a>
            <a href="#">Terms</a>
            <a href="mailto:hello@betterleaf.app">Contact</a>
          </nav>
        </div>
      </footer>

      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.doc,.docx,application/pdf"
        hidden
        onChange={onFileChange}
      />
      <div className={`toast${toast ? " show" : ""}`} role="status">
        {toast}
      </div>
    </div>
  );
}
