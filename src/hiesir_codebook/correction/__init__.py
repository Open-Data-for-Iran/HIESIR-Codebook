"""Correction: ``output/1_extracted/`` + ``curated/2_corrected/`` -> ``output/2_corrected/``.

The build (:mod:`.correct`) reads every questionnaire into one polars table,
fixes its structure (:mod:`.corrections`: ``corrections.csv``, and the
structure check with ``header_exceptions.csv``), then takes each description
through the label steps, one column each: ``canonical``, ``house_style``
(:mod:`.rules`), ``letters``, ``words`` and ``spelling``.  The fixes they
apply are tables of find -> replace (:mod:`.fixes`).

The ``autocorrect`` command (:mod:`.words`) writes the two files of
``output/2_corrected/autocorrect/`` with hazm's word list (:mod:`.lexicon`), so
the build itself needs none of hazm's data: ``canonical.csv`` (one wording per
group of labels, :mod:`.canonical`) and ``words.csv`` (every automatic word
fix, from a chain of finders: learned and folded, :mod:`.canonical`; hazm's
rules, :mod:`.hazm_rules`).  :mod:`.text` holds what all of them mean by a
word and the folds that make two spellings one key.
"""
