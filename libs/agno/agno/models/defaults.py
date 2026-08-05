# Upstream removed this module in agno v2.7 (inlined the literal at its one call site).
# Kept here as a backward-compat shim: this constant had a real internal caller as of our
# v2.6.20 baseline, so downstream code may import it directly too. New code should not
# depend on this - pass a model id explicitly instead.
DEFAULT_OPENAI_MODEL_ID: str = "gpt-5.4-mini"
