
class SuggestionGenerator:
    def generate(self, analysis):
        suggestions = []

        if analysis["missing_readme"]:
            suggestions.append("Create a README.md to document your project.")

        if analysis["python"] > 50:
            suggestions.append("Consider splitting large modules into smaller packages.")

        if analysis["markdown"]:
            suggestions.append("Add documentation for contributors.")

        return {"suggestions": suggestions}