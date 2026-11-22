"""Correction: ``output/1_extracted/`` + ``curated/2_corrected/`` -> ``output/2_corrected/``.

``correct`` runs each questionnaire through five steps, in this order:
``corrections`` (``corrections.csv``, and the structure check with
``header_exceptions.csv``), ``canonical`` (one wording for labels printed in
several ways, ``output/2_corrected/autocorrect/canonical.csv``), ``rules``
(the house style), ``autocorrect``
(``output/2_corrected/autocorrect/hazm.csv``, written from hazm's word list)
and ``spelling`` (``spelling.csv``).
"""
