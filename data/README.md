# data/

This folder holds all the data the assistant works with. It's split into three parts:

## rulebooks/
The actual legal text of GDPR and HIPAA (the real rules and articles). This is the "source of
truth" the assistant searches through when it needs to cite a specific rule to back up a finding.

## documents_to_check/
Sample privacy policies, contracts, and other documents we want to *audit* — i.e. the files the
assistant will scan to look for compliance gaps. These are inputs, not answers.

## benchmarks/
Evaluation datasets that already have known, correct answers. We use these to test how accurate
the assistant is — by comparing what it says to what the "correct" answer already is — instead of
just trusting it blindly.
