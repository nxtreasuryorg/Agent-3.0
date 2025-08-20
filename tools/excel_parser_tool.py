"""Excel Parser Tool for processing financial data from Excel files."""
import pandas as pd
import json
from typing import Dict, Any, List, Optional
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import io

class ExcelParserInput(BaseModel):
    """Input schema for Excel Parser Tool."""
    file_path: str = Field(description="Path to the Excel file")
    sheet_name: Optional[str] = Field(default=None, description="Specific sheet to parse")

class ExcelParserTool(BaseTool):
    name: str = "Excel Parser Tool"
    description: str = """
    Parse and normalize Excel files containing financial data.
    Handles various formats, detects sheets/headers dynamically,
    and extracts structured data for financial analysis.
    """
    args_schema: type[BaseModel] = ExcelParserInput

    def _run(self, file_path: str, sheet_name: Optional[str] = None) -> Dict[str, Any]:
        """Parse Excel file and extract financial data."""
        try:
            # Read Excel file from path
            xl_file = pd.ExcelFile(file_path)
            sheets = xl_file.sheet_names
            
            result = {
                "sheets": sheets,
                "data": {},
                "summary": {}
            }
            
            # Parse specified sheet or all sheets
            sheets_to_parse = [sheet_name] if sheet_name else sheets
            
            for sheet in sheets_to_parse:
                if sheet in sheets:
                    df = pd.read_excel(file_path, sheet_name=sheet)
                    
                    # Clean and normalize data
                    df = df.dropna(how='all')  # Remove empty rows
                    df = df.dropna(axis=1, how='all')  # Remove empty columns
                    
                    # Detect numeric columns
                    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                    
                    # Store parsed data
                    result["data"][sheet] = {
                        "columns": df.columns.tolist(),
                        "rows": df.shape[0],
                        "numeric_columns": numeric_cols,
                        "records": df.to_dict(orient='records')
                    }
                    
                    # Generate summary statistics for numeric columns
                    if numeric_cols:
                        summary = {}
                        for col in numeric_cols:
                            summary[col] = {
                                "sum": float(df[col].sum()),
                                "mean": float(df[col].mean()),
                                "min": float(df[col].min()),
                                "max": float(df[col].max()),
                                "count": int(df[col].count())
                            }
                        result["summary"][sheet] = summary
            
            # Add metadata
            result["metadata"] = {
                "total_sheets": len(sheets),
                "parsed_sheets": len(sheets_to_parse),
                "success": True
            }
            
            return result
            
        except Exception as e:
            return {
                "error": str(e),
                "success": False,
                "metadata": {"error_type": type(e).__name__}
            }
