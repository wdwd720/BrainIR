"""sha256 of `brainir_v1.py`, the BrainIR v1 method file (review B finding B1).

The method records this value in every result (`diagnostics["code"]`) and in its method info, so that each result names the file
that produced it. A method module may not read files (static rule of tests/test_budget_integrity.py), so the value is written here
when the method file is frozen; tests/test_method_brainir_v1.py checks that it equals the sha256 of the file as it is.
"""

METHOD_FILE_SHA256 = "4bfcf81628aba7684688fefd113eddd705a13e250f119caea2050cd65d84d2a7"
