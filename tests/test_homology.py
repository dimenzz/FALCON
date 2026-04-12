from pathlib import Path

from falcon.homology.search import HomologyHit, parse_hits_tsv, run_mmseqs_search


def test_parse_hits_tsv_casts_mmseqs_columns(tmp_path: Path) -> None:
    hits_path = tmp_path / "raw_hits.tsv"
    hits_path.write_text(
        "q1\ttarget90\t87.5\t120\t0.95\t0.82\t1e-20\t180\t130\t145\n",
        encoding="utf-8",
    )

    hits = parse_hits_tsv(hits_path, search_level=90)

    assert hits == [
        HomologyHit(
            query_id="q1",
            target_id="target90",
            pident=87.5,
            alnlen=120,
            qcov=0.95,
            tcov=0.82,
            evalue=1e-20,
            bits=180.0,
            qlen=130,
            tlen=145,
            search_level=90,
            rank=1,
        )
    ]


def test_run_mmseqs_search_invokes_easy_search_with_configured_defaults(tmp_path: Path) -> None:
    fake_mmseqs = tmp_path / "mmseqs"
    log_path = tmp_path / "args.txt"
    fake_mmseqs.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' \"$@\" > \"$MMSEQS_LOG\"\n"
        "printf 'q1\\ttarget90\\t80.0\\t10\\t1.0\\t0.9\\t1e-5\\t50\\t10\\t10\\n' > \"$4\"\n",
        encoding="utf-8",
    )
    fake_mmseqs.chmod(0o755)
    query = tmp_path / "query.faa"
    query.write_text(">q1\nMKT\n", encoding="utf-8")
    output = tmp_path / "raw_hits.tsv"
    tmp_dir = tmp_path / "tmp"

    run_mmseqs_search(
        mmseqs_path=fake_mmseqs,
        query_fasta=query,
        target_db=tmp_path / "target_db",
        output_tsv=output,
        tmp_dir=tmp_dir,
        sensitivity=7.5,
        evalue=1e-3,
        max_seqs=5000,
        threads=8,
        env={"MMSEQS_LOG": str(log_path)},
        log_dir=tmp_path / "logs",
    )

    args = log_path.read_text(encoding="utf-8").splitlines()
    assert args[:4] == ["easy-search", str(query), str(tmp_path / "target_db"), str(output)]
    assert "-s" in args
    assert "7.5" in args
    assert "-e" in args
    assert "0.001" in args
    assert "--max-seqs" in args
    assert "5000" in args
    assert "--threads" in args
    assert "8" in args
    assert output.exists()


def test_run_mmseqs_search_captures_tool_logs(tmp_path: Path) -> None:
    fake_mmseqs = tmp_path / "mmseqs"
    fake_mmseqs.write_text(
        "#!/bin/sh\n"
        "printf 'mmseqs progress\\n'\n"
        "printf 'mmseqs diagnostics\\n' >&2\n"
        "printf 'q1\\ttarget90\\t80.0\\t10\\t1.0\\t0.9\\t1e-5\\t50\\t10\\t10\\n' > \"$4\"\n",
        encoding="utf-8",
    )
    fake_mmseqs.chmod(0o755)
    query = tmp_path / "query.faa"
    query.write_text(">q1\nMKT\n", encoding="utf-8")

    trace = run_mmseqs_search(
        mmseqs_path=fake_mmseqs,
        query_fasta=query,
        target_db=tmp_path / "target_db",
        output_tsv=tmp_path / "raw_hits.tsv",
        tmp_dir=tmp_path / "tmp",
        sensitivity=7.5,
        evalue=1e-3,
        max_seqs=5000,
        threads=8,
        log_dir=tmp_path / "logs",
    )

    assert "mmseqs progress" in Path(trace["stdout_log"]).read_text(encoding="utf-8")
    assert "mmseqs diagnostics" in Path(trace["stderr_log"]).read_text(encoding="utf-8")
