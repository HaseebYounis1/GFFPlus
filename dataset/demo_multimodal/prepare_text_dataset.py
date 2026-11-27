#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generic Text Dataset Builder for GFF+ Multimodal Point DataLoader.

Converts ANY text dataset into a GFF+-ready bundle:
  - <name>.csv          (numeric stylometric + TF-IDF features, `file` column, `Category`)
  - media/<file>.txt    (individual readable text files linked to each projected point)
  - <name>_media.zip    (ready to upload via GFF+'s yellow ZIP button)

Usage examples:
  1. Generate the built-in 80-document exemplary corpus:
       python dataset/demo_multimodal/prepare_text_dataset.py

  2. Convert ANY folder of .txt/.md/.json files (subfolders become Category labels):
       python dataset/demo_multimodal/prepare_text_dataset.py \\
           --input-dir path/to/my_docs --output-dir out_folder --name my_corpus

  3. Convert ANY CSV with a text column (e.g. reviews, abstracts, clinical notes):
       python dataset/demo_multimodal/prepare_text_dataset.py \\
           --input-csv reviews.csv --text-col review_text --label-col sentiment \\
           --output-dir out_folder --name reviews_gff
"""

import argparse
import math
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

TEXT_EXTENSIONS = {".txt", ".md", ".json", ".csv", ".tsv", ".log", ".xml", ".yaml", ".yml", ".rst"}


def extract_stylometric_features(text: str) -> dict:
    """Compute domain-agnostic linguistic/structural features for any text."""
    raw = str(text or "")
    chars = len(raw)
    words = re.findall(r"[A-Za-z0-9']+", raw)
    n_words = len(words)
    lower_words = [w.lower() for w in words]
    unique_words = len(set(lower_words))
    sentences = [s.strip() for s in re.split(r"[.!?]+", raw) if s.strip()]
    n_sent = max(1, len(sentences))
    long_words = sum(1 for w in words if len(w) >= 7)
    digits = sum(1 for ch in raw if ch.isdigit())
    uppers = sum(1 for ch in raw if ch.isupper())
    puncts = sum(1 for ch in raw if ch in ",.;:!?-()[]\"'")

    return {
        "word_count": float(n_words),
        "char_count": float(chars),
        "sentence_count": float(n_sent),
        "avg_word_len": round(sum(len(w) for w in words) / max(1, n_words), 4),
        "avg_sentence_len": round(n_words / float(n_sent), 4),
        "lexical_diversity": round(unique_words / max(1, n_words), 4),
        "long_word_ratio": round(long_words / max(1, n_words), 4),
        "uppercase_ratio": round(uppers / max(1, chars), 4),
        "digit_ratio": round(digits / max(1, chars), 4),
        "punctuation_density": round(puncts / max(1, chars), 4),
    }


def _safe_filename(name: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(name or "")).strip("_")
    return cleaned or fallback


def build_gff_text_bundle(
    records: list,
    output_dir: Path,
    dataset_name: str = "text_dataset",
    max_tfidf_features: int = 24,
    extra_label_cols: list = None,
) -> Path:
    """Generic pipeline: given a list of dicts with keys
    `file`, `text`, `Category` (+ optional extra label columns), writes:
      - output_dir / f"{dataset_name}.csv"
      - output_dir / "media" / <file>
      - output_dir / f"{dataset_name}_media.zip"
    """
    if not records:
        raise ValueError("No text documents found to build dataset.")

    output_dir = Path(output_dir)
    media_dir = output_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    extra_label_cols = extra_label_cols or []

    texts = [str(r["text"]) for r in records]
    style_rows = [extract_stylometric_features(t) for t in texts]

    # Generic TF-IDF term features (interpretable feature names for the Feature Graph)
    # Use max_df=0.85, min_df=2 on normal corpora to filter boilerplate headers automatically.
    use_df_filter = len(texts) >= 6
    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=max_tfidf_features,
        max_df=0.85 if use_df_filter else 1.0,
        min_df=2 if use_df_filter else 1,
        sublinear_tf=True,
        token_pattern=r"(?u)\b[a-zA-Z]{4,}\b",
    )
    tfidf_matrix = vectorizer.fit_transform(texts).toarray()
    tfidf_names = [f"tfidf_{term}" for term in vectorizer.get_feature_names_out()]

    rows = []
    zip_path = output_dir / f"{dataset_name}_media.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for idx, rec in enumerate(records):
            fname = _safe_filename(rec.get("file", ""), f"doc_{idx:03d}.txt")
            if "." not in fname:
                fname += ".txt"
            doc_text = str(rec["text"])
            (media_dir / fname).write_text(doc_text, encoding="utf-8")
            zf.writestr(fname, doc_text.encode("utf-8"))

            row = {"file": fname}
            row.update(style_rows[idx])
            for j, col_name in enumerate(tfidf_names):
                row[col_name] = round(float(tfidf_matrix[idx, j]), 5)
            for col in extra_label_cols:
                row[col] = rec.get(col, "")
            row["Category"] = rec.get("Category", "document")
            rows.append(row)

    df = pd.DataFrame(rows)
    csv_path = output_dir / f"{dataset_name}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8")
    return csv_path


def load_from_directory(input_dir: Path) -> list:
    """Read any folder of text files; subfolder names become Category labels."""
    root = Path(input_dir)
    records = []
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS)
    for idx, fp in enumerate(files):
        rel = fp.relative_to(root)
        category = rel.parts[0] if len(rel.parts) > 1 else "document"
        fname = _safe_filename(f"{idx:03d}_{fp.name}", f"doc_{idx:03d}.txt")
        records.append({
            "file": fname,
            "text": fp.read_text(encoding="utf-8", errors="replace"),
            "Category": category,
        })
    return records


def load_from_csv(input_csv: Path, text_col: str, label_col: str = None, extra_cols: list = None) -> list:
    """Read any CSV with a text column and optional label column."""
    df = pd.read_csv(input_csv, encoding="utf-8-sig")
    if text_col not in df.columns:
        raise ValueError(f"Text column '{text_col}' not found in {input_csv}. Available: {list(df.columns)}")
    extra_cols = [c for c in (extra_cols or []) if c in df.columns]
    records = []
    for idx, row in df.iterrows():
        cat = str(row[label_col]) if (label_col and label_col in df.columns) else "document"
        cat_slug = re.sub(r"[^A-Za-z0-9]+", "_", cat).strip("_").lower()[:24] or "doc"
        rec = {
            "file": f"doc_{idx:03d}_{cat_slug}.txt",
            "text": str(row[text_col] if pd.notna(row[text_col]) else ""),
            "Category": cat,
        }
        for c in extra_cols:
            rec[c] = row[c]
        records.append(rec)
    return records


def generate_demo_corpus() -> list:
    """Build an exemplary 80-document multi-topic text corpus (4 topics x 20 docs)
    with realistic headlines, metadata, rich paragraphs, and a secondary `style_tone` label."""
    rng = np.random.RandomState(7)

    topics = {
        "Science_Space": {
            "subjects": [
                "orbital telescope observatory", "deep space propulsion probe", "Martian regolith rover",
                "exoplanet atmospheric spectrometer", "solar flare magnetosphere monitor",
                "lunar crater ice core mission", "gravitational wave interferometer", "asteroid trajectory radar",
            ],
            "verbs": ["detected", "mapped", "measured", "calibrated", "captured", "confirmed"],
            "findings": [
                "high-altitude methane plumes and silicate dust layers across the northern basin",
                "unexpected gamma-ray bursts originating from a binary neutron star merger",
                "crystalline water ice deposits preserved beneath shadowed polar craters",
                "subtle orbital resonance shifts indicating a previously unseen rocky exoplanet",
                "intense coronal plasma streams interacting with planetary magnetic fields",
                "isotopic oxygen signatures consistent with ancient subterranean aquifers",
            ],
            "contexts": [
                "Astronomers and planetary physicists reviewed telemetry streams across 14 ground antennas.",
                "Mission engineers adjusted solar array pitch and thermal shields to extend orbital endurance.",
                "Spectral analysis confirmed repeatable absorption bands across infrared and ultraviolet channels.",
                "The observatory consortium published calibrated FITS archives for independent verification.",
            ],
        },
        "Health_Medicine": {
            "subjects": [
                "multi-center clinical trial", "cardiology biomarker study", "oncology immunotherapy cohort",
                "neurology imaging registry", "pediatric vaccine surveillance",
                "metabolic insulin resistance panel", "pulmonary rehabilitation protocol", "genomic screening clinic",
            ],
            "verbs": ["demonstrated", "validated", "observed", "recorded", "evaluated", "reported"],
            "findings": [
                "a 34 percent reduction in hospital readmissions among high-risk outpatient cohorts",
                "improved systolic blood pressure control with minimal adverse metabolic side effects",
                "earlier tumor regression when combining targeted monoclonal therapy with checkpoint blockade",
                "measurable recovery in cognitive memory scores following structured sleep intervention",
                "durable antibody titers lasting 18 months across elderly and immunocompromised patients",
                "faster diagnostic turnaround using point-of-care plasma protein assays in emergency wards",
            ],
            "contexts": [
                "Clinicians and biostatisticians monitored patient safety endpoints over a 24-week follow-up.",
                "Hospital ethics boards audited dosing compliance, laboratory panels, and symptom diaries.",
                "Physicians noted that preventative screening lowered acute care utilization across clinics.",
                "Peer-reviewed medical guidelines are being updated to incorporate these clinical outcomes.",
            ],
        },
        "Tech_AI": {
            "subjects": [
                "transformer inference compiler", "federated neural network cluster", "quantized vision backbone",
                "autonomous robotics perception stack", "distributed vector search engine",
                "edge silicon accelerator chip", "explainable gradient boosting framework", "multimodal embedding pipeline",
            ],
            "verbs": ["accelerated", "benchmarked", "optimized", "deployed", "compressed", "streamlined"],
            "findings": [
                "low-latency token generation at 4-bit precision with negligible perplexity degradation",
                "sub-millisecond approximate nearest-neighbor retrieval across 50 million dense embeddings",
                "interpretable feature attribution scores that align closely with domain expert rankings",
                "energy-efficient matrix multiplication reducing datacenter GPU power draw by 42 percent",
                "robust out-of-distribution generalization under noisy sensor inputs and domain shifts",
                "zero-downtime rolling updates across containerized microservice inference nodes",
            ],
            "contexts": [
                "Software engineers profiled memory bandwidth, cache locality, and kernel fusion throughput.",
                "Open-source benchmarks verified reproducible accuracy across standard validation suites.",
                "Security teams audited API sandboxing, deterministic seeds, and model governance logs.",
                "Production telemetry confirmed stable tail latency during peak concurrent request loads.",
            ],
        },
        "Sports_Athletics": {
            "subjects": [
                "championship finals matchup", "marathon pacing strategy", "national swimming relay squad",
                "premier football tactical press", "grand slam tennis semifinal",
                "cycling mountain stage peloton", "basketball fourth-quarter comeback", "track and field decathlon",
            ],
            "verbs": ["delivered", "clinched", "executed", "secured", "orchestrated", "sustained"],
            "findings": [
                "a dramatic stoppage-time goal following a rapid counterattack down the right flank",
                "a personal-best negative split over the final 10 kilometers despite gusting headwinds",
                "dominant defensive rebounding and 88 percent free-throw accuracy in overtime",
                "flawless baton exchanges and underwater dolphin kicks that broke the stadium record",
                "relentless baseline winners and crisp net volleys across five grueling sets",
                "coordinated team drafting up the steep alpine climb to capture the yellow jersey",
            ],
            "contexts": [
                "Coaches credited off-season conditioning, sprint drills, and video match analysis.",
                "Supporters packed the arena as official timing boards flashed the decisive scoreline.",
                "Sports physiologists tracked heart-rate recovery, stride cadence, and hydration intervals.",
                "Analysts highlighted disciplined teamwork and composure under intense tournament pressure.",
            ],
        },
    }

    tones = [
        ("analytical", "Technical Note: Quantitative indicators and controlled comparisons highlight clear structural separation."),
        ("reporting", "Field Report: Correspondents gathered direct observations and verified records from primary sources."),
        ("briefing", "Executive Summary: Key takeaways are distilled below for rapid cross-disciplinary review."),
    ]

    records = []
    doc_idx = 0
    for topic_name, vocab in topics.items():
        slug = topic_name.lower()
        for k in range(20):
            subj = vocab["subjects"][k % len(vocab["subjects"])]
            verb = vocab["verbs"][(k + 2) % len(vocab["verbs"])]
            finding = vocab["findings"][(k + 3) % len(vocab["findings"])]
            ctx1 = vocab["contexts"][k % len(vocab["contexts"])]
            ctx2 = vocab["contexts"][(k + 1) % len(vocab["contexts"])]
            tone_label, tone_line = tones[k % len(tones)]
            year = 2023 + (k % 4)
            month = 1 + (k % 12)
            day = 1 + ((k * 3) % 27)
            ref_num = 100 + doc_idx

            # Add slight controlled length variation for realistic stylometric diversity
            extra_detail = ""
            if k % 2 == 0:
                extra_detail = (
                    f"\n\nAdditional Context: Follow-up review #{ref_num} compared {subj} metrics "
                    f"against prior baseline cohorts from {year - 1}, confirming consistent patterns."
                )

            headline = f"{subj.title()} {verb.title()} Key Breakthrough in {topic_name.replace('_', ' & ')}"
            body = (
                f"Title: {headline}\n"
                f"Topic: {topic_name.replace('_', ' & ')} | Tone: {tone_label.title()} | Date: {year}-{month:02d}-{day:02d} | Ref: DOC-{ref_num}\n"
                f"{'=' * 72}\n\n"
                f"{tone_line}\n\n"
                f"A recent {subj} {verb} {finding}. {ctx1} {ctx2}"
                f"{extra_detail}\n"
            )
            records.append({
                "file": f"doc_{doc_idx:03d}_{slug}.txt",
                "text": body,
                "style_tone": tone_label,
                "Category": topic_name,
            })
            doc_idx += 1

    # Shuffle deterministically so classes are interleaved nicely
    order = rng.permutation(len(records))
    return [records[i] for i in order]


def main():
    parser = argparse.ArgumentParser(description="Build a GFF+ multimodal text dataset (CSV + media ZIP).")
    parser.add_argument("--input-dir", type=str, default=None, help="Folder of .txt/.md/.json files (optional)")
    parser.add_argument("--input-csv", type=str, default=None, help="CSV file with a text column (optional)")
    parser.add_argument("--text-col", type=str, default="text", help="Text column name when using --input-csv")
    parser.add_argument("--label-col", type=str, default="Category", help="Label column name when using --input-csv")
    parser.add_argument("--output-dir", type=str, default=None, help="Destination directory")
    parser.add_argument("--name", type=str, default="text_80", help="Output dataset base name")
    parser.add_argument("--max-tfidf-features", type=int, default=24, help="Number of top TF-IDF term features")
    args = parser.parse_args()

    default_out = Path(__file__).resolve().parent / "text_80_documents"
    out_dir = Path(args.output_dir) if args.output_dir else default_out
    extra_cols = []

    if args.input_dir:
        records = load_from_directory(Path(args.input_dir))
    elif args.input_csv:
        records = load_from_csv(Path(args.input_csv), args.text_col, args.label_col)
    else:
        records = generate_demo_corpus()
        extra_cols = ["style_tone"]

    csv_path = build_gff_text_bundle(
        records=records,
        output_dir=out_dir,
        dataset_name=args.name,
        max_tfidf_features=args.max_tfidf_features,
        extra_label_cols=extra_cols,
    )
    print(f"Created GFF+ text dataset ({len(records)} docs):")
    print(f"  CSV : {csv_path}")
    print(f"  ZIP : {out_dir / (args.name + '_media.zip')}")
    print(f"  Docs: {out_dir / 'media'}")


if __name__ == "__main__":
    main()
