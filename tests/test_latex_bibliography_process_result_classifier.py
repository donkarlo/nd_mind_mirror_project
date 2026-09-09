from nd_mind_mirror.core.render.latex.diagnostic.latex_bibliography_process_result_classifier import (
    LatexBibliographyProcessResultClassifier,
)


def test_bibtex_missing_entry_warning_is_recoverable():
    output = '''
Warning--I didn't find a database entry for "missing-key"
Warning--empty publisher in some-entry
(There were 2 warnings)
'''

    classifier = LatexBibliographyProcessResultClassifier()

    assert classifier.is_recoverable_warning_exit("bibtex", output)


def test_biber_warning_is_recoverable():
    output = '''
WARN - Datamodel: Entry 'sample': Missing mandatory field 'author'
INFO - WARNINGS: 1
'''

    classifier = LatexBibliographyProcessResultClassifier()

    assert classifier.is_recoverable_warning_exit("biber", output)


def test_bibliography_hard_error_is_not_recoverable():
    output = '''
I couldn't open database file missing.bib
I found no database files---while reading file preview.aux
(There were 2 error messages)
'''

    classifier = LatexBibliographyProcessResultClassifier()

    assert not classifier.is_recoverable_warning_exit("bibtex", output)


def test_non_bibliography_phase_is_not_recoverable():
    output = "Package natbib Warning: Citation `missing' undefined."

    classifier = LatexBibliographyProcessResultClassifier()

    assert not classifier.is_recoverable_warning_exit("latex2", output)
