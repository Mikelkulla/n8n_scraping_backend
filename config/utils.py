# config/utils.py
import pandas as pd
import os
import logging

def load_csv(input_csv, output_csv, required_columns=None):
    """
    Loads a CSV file for processing, using the output CSV as input if it exists.
    Ensures the output directory exists and validates required columns.

    Parameters:
    -----------
    input_csv (str): Path to the input CSV file.
    output_csv (str): Path to save the updated CSV file.
    required_columns (list, optional): List of column names that must exist in the CSV.

    Returns:
    --------
    tuple: (pd.DataFrame, str) - The loaded DataFrame and the resolved input CSV path,
           or (None, None) if an error occurs.
    """
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_csv), exist_ok=True)

        # Check if output file exists and use it as input if available
        if os.path.exists(output_csv):
            logging.info(f"Output file '{output_csv}' exists, using it as input")
            resolved_input_csv = output_csv
        else:
            logging.info(f"No output file found, using input file '{input_csv}'")
            resolved_input_csv = input_csv

        # Read the CSV file
        logging.info(f"Reading CSV: {resolved_input_csv}")
        df = pd.read_csv(resolved_input_csv, dtype=str, keep_default_na=False)

        # Validate required columns if provided
        if required_columns:
            for col in required_columns:
                if col not in df.columns:
                    raise ValueError(f"Column '{col}' not found in CSV")

        return df, resolved_input_csv

    except FileNotFoundError:
        logging.error(f"Input CSV file '{resolved_input_csv}' not found.")
        print(f"Error: Input CSV file '{resolved_input_csv}' not found.")
        return None, None
    except Exception as e:
        logging.error(f"Error loading CSV: {e}")
        print(f"Error loading CSV: {e}")
        return None, None
    
