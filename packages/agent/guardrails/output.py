class OutputValidator:
    def __init__(self, validation_pipeline, fact_check_llm=None):
        self.validation = validation_pipeline
        self.fact_check_llm = fact_check_llm

    async def validate(self, result, expectation=None, context=""):
        if expectation and not await self.validation.validate(expectation, result):
            return False
        if self.fact_check_llm and isinstance(result, str) and context:
            resp = await self.fact_check_llm.complete([
                {"role": "system", "content": "Is the statement fully supported by the context? Answer only 'yes' or 'no'."},
                {"role": "user", "content": f"Context: {context}\nStatement: {result}"}
            ])
            if resp.strip().lower() == "no":
                return False
        return True
