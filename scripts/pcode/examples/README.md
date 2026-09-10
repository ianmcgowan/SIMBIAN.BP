# UniBasic examples extracted from the Commands Reference

533 code examples pulled from *UniData UniBasic Commands Reference v8.2.1*
(`UniData_UniBasicCommandsRefGuide_V821.pdf`), one per file, named
`<COMMAND>_<nn>.bp`.  Regenerate with `../extract_examples.py` after

    pdftotext -layout UniData_UniBasicCommandsRefGuide_V821.pdf /tmp/ubcmd_layout.txt

## Caveats

These are documentation *snippets*, not whole programs:

* many are fragments (a `CASE` arm, a `FOR` body split across a PDF page) and
  reference labels / variables / subroutines defined elsewhere
* a few carry PDF artefacts (a running-header word merged into a line, an
  intro sentence fragment on line 1) despite the extractor's filters
* indentation can jump mid-example where the PDF page broke (harmless — the
  compiler ignores it)

`../check_examples.sh` compiles them all through the `PCLAB` directory file
(u-mode) and writes `../examples.compiles.txt` / `../examples.fails.txt`.
As of extraction: **403 / 533 compile** (with `--stub`, which appends
`label:` / `RETURN` stubs for undefined-label fragments; 391 without).

## Roundtrip

For the decompiler roundtrip: compile an example, then
`pdec.py lab/_<name>` and compare with the source.
