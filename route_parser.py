# route_parser.py (Revised Version)
import re
import io
import sys
from contextlib import redirect_stderr

# --- clean_route_string function remains unchanged ---
def clean_route_string(route_string, destination_code):
    if route_string == "Rou" or not route_string or not destination_code:
        return route_string
    last_occurrence_index = route_string.rfind(destination_code)
    if last_occurrence_index != -1:
        dest_code_end_index = last_occurrence_index + len(destination_code)
        return route_string[:dest_code_end_index].rstrip()
    else:
        return route_string.rstrip()
# --- end of clean_route_string ---

def parse_route_content(input_content):
    """
    Parses route information from a string content.

    Args:
        input_content: A string containing the entire text file content.

    Returns:
        A tuple containing:
        - output_csv_string: A string with the generated CSV data.
        - log_messages: A string containing captured warnings/errors.
    """
    output_lines = []
    log_stream = io.StringIO() # Capture stderr messages

    with redirect_stderr(log_stream):
        try:
            # Split lines, keeping line endings consistent might not matter
            # due to strip(), but splitlines() is standard for string input.
            lines = input_content.splitlines()
        except Exception as e:
            print(f"An unexpected error occurred splitting input content: {e}", file=sys.stderr)
            return "", log_stream.getvalue()

        mode = 'FIND_DISTANCE'
        current_route_info = {}
        route_parts = []

        for line_num, line_content in enumerate(lines, start=1):
            line_stripped = line_content.strip()
            process_this_line_in_find_distance = False # Reset flag for each line

            # === FIND_DISTANCE Mode Logic ===
            if mode == 'FIND_DISTANCE':
                # Skip irrelevant lines
                if not line_stripped or "ROUTES FOR AIRLINE:" in line_content or line_stripped.startswith('\f'):
                    continue # Skip to next line

                distance_marker = " Distance: "
                if distance_marker in line_content:
                    try:
                        parts = line_content.split(distance_marker, 1)
                        route_id_part = parts[0].strip()
                        distance = parts[1].strip()

                        matches = re.findall(r'([A-Z]{4})', route_id_part)
                        if not matches:
                            print(f"Warning line {line_num}: Could not find any 4-uppercase-letter destination code in '{route_id_part}'. Skipping.", file=sys.stderr)
                            continue # Skip to next line

                        dest_code = matches[-1]
                        dest_index = route_id_part.rfind(dest_code)
                        # This check might be redundant if findall worked, but safe
                        if dest_index == -1:
                            print(f"Warning line {line_num}: Internal logic error finding index for '{dest_code}' in '{route_id_part}'. Skipping.", file=sys.stderr)
                            continue # Skip to next line

                        origin = route_id_part[:dest_index].strip()
                        suffix = route_id_part[dest_index + 4:].strip()
                        # Ensure origin is max 4 chars, left-padded with spaces if shorter
                        origin_formatted = origin[:4].ljust(4)

                        # Store info for the route we just found
                        current_route_info = {
                            'origin': origin_formatted,
                            'dest': dest_code,
                            'suffix': suffix,
                            'distance': distance,
                            'line_num': line_num # Store line number where route started
                        }
                        route_parts = [] # Reset parts for the new route
                        mode = 'READ_ROUTE' # Switch mode to read the route details

                    except Exception as e:
                        print(f"Error parsing distance line {line_num}: {line_content.strip()}\nError: {e}", file=sys.stderr)
                        # Reset state and stay in FIND_DISTANCE mode
                        current_route_info = {}
                        route_parts = []
                        mode = 'FIND_DISTANCE'
                # If line is not blank/separator and not a distance line in FIND_DISTANCE mode,
                # it might be unexpected content. Log it? Or just ignore and continue?
                # Current logic implicitly ignores it and proceeds to the next line.

            # === READ_ROUTE Mode Logic ===
            elif mode == 'READ_ROUTE':
                finalized_route_string = None # Flag to check if we finalized a route in this iteration

                # Case 1: Blank line signifies end of current route block
                if not line_stripped:
                    if route_parts: # Only finalize if we have parts
                        finalized_route_string = " ".join(route_parts)
                    # If no route_parts, blank line is just ignored.
                    mode = 'FIND_DISTANCE' # Always switch back after a blank line

                # Case 2: Explicit "Routing not built" marker
                elif line_stripped.startswith("Routing has not been built"):
                    finalized_route_string = "Rou" # Special marker
                    mode = 'FIND_DISTANCE' # Switch back

                # Case 3: Found a separator line (new distance, airline header, form feed)
                # This signifies the end of the *previous* route block AND the start of something new.
                elif " Distance: " in line_content or \
                     "ROUTES FOR AIRLINE:" in line_content or \
                     line_stripped.startswith('\f'):

                    if route_parts: # Finalize the route gathered so far
                        finalized_route_string = " ".join(route_parts)
                    else:
                        # This happens if a distance line immediately follows another distance line
                        # Or if a route block was empty before a separator.
                        print(f"Warning after line {current_route_info.get('line_num', 'N/A')}: Found separator line {line_num} immediately after route start or with empty route details. Record may be incomplete.", file=sys.stderr)

                    # This separator line needs to be processed by FIND_DISTANCE
                    mode = 'FIND_DISTANCE'
                    process_this_line_in_find_distance = True

                # Case 4: Regular line containing route part
                else:
                    route_parts.append(line_stripped)

                # --- Finalize and output if needed ---
                if finalized_route_string is not None:
                    cleaned_route_string = clean_route_string(
                        finalized_route_string,
                        current_route_info.get('dest') # Use .get for safety
                    )
                    # Ensure current_route_info exists before accessing keys
                    if current_route_info:
                        info = current_route_info
                        output_line = f"C,{info['origin']},{info['dest']},{info['suffix']},{info['distance']},{cleaned_route_string}"
                        output_lines.append(output_line)
                    else:
                        # Should not happen if logic is correct, but good to check
                         print(f"Warning line {line_num}: Trying to finalize route but current_route_info is missing.", file=sys.stderr)

                    route_parts = [] # Reset parts immediately after finalizing

            # === Reprocessing Logic (if triggered from READ_ROUTE) ===
            # This block executes *after* the main mode logic for the current line,
            # if the flag was set.
            if process_this_line_in_find_distance:
                # **Critical**: Reset state variables before attempting re-processing the line
                mode = 'FIND_DISTANCE' # Ensure mode is FIND_DISTANCE
                current_route_info = {} # Clear previous route info
                route_parts = []        # Clear any route parts

                # Now, re-evaluate the *current* line under FIND_DISTANCE rules
                if not line_stripped or "ROUTES FOR AIRLINE:" in line_content or line_stripped.startswith('\f'):
                    pass # It's just a separator, do nothing else this iteration

                elif " Distance: " in line_content:
                     distance_marker = " Distance: "
                     try:
                         parts = line_content.split(distance_marker, 1)
                         route_id_part = parts[0].strip()
                         distance = parts[1].strip()
                         matches = re.findall(r'([A-Z]{4})', route_id_part)

                         if not matches:
                             print(f"Warning line {line_num} (reprocess): Could not find any 4-uppercase-letter destination code in '{route_id_part}'. Skipping.", file=sys.stderr)
                             continue # Skip to the next line in the main loop

                         dest_code = matches[-1]
                         dest_index = route_id_part.rfind(dest_code)

                         if dest_index == -1:
                             print(f"Warning line {line_num} (reprocess): Internal logic error finding index for '{dest_code}' in '{route_id_part}'. Skipping.", file=sys.stderr)
                             continue # Skip to the next line

                         # Only proceed if matches and index are found
                         origin = route_id_part[:dest_index].strip()
                         suffix = route_id_part[dest_index + 4:].strip()
                         origin_formatted = origin[:4].ljust(4)

                         # Store the newly parsed info
                         current_route_info = {
                             'origin': origin_formatted,
                             'dest': dest_code,
                             'suffix': suffix,
                             'distance': distance,
                             'line_num': line_num
                         }
                         route_parts = [] # Ensure route parts are empty for the new route
                         mode = 'READ_ROUTE' # Switch mode for the *next* line iteration

                     except Exception as e:
                         print(f"Error parsing distance line {line_num} on re-process: {line_content.strip()}\nError: {e}", file=sys.stderr)
                         # Reset state and ensure mode is FIND_DISTANCE for next iteration
                         current_route_info = {}
                         route_parts = []
                         mode = 'FIND_DISTANCE'
                # else:
                # This line was a separator but not a distance line (e.g. AIRLINE header)
                # State has been reset, mode is FIND_DISTANCE, we just continue to next line.


        # === End of Loop - Handle final route block ===
        # If the file ended while we were reading route parts
        if mode == 'READ_ROUTE' and route_parts:
            finalized_route_string = " ".join(route_parts)
            cleaned_route_string = clean_route_string(
                finalized_route_string,
                current_route_info.get('dest') # Use .get for safety
            )
            # **Critical**: Check if current_route_info actually has data
            if current_route_info:
                info = current_route_info
                output_line = f"C,{info['origin']},{info['dest']},{info['suffix']},{info['distance']},{cleaned_route_string}"
                output_lines.append(output_line)
            else:
                 # This could happen if the file ends strangely after a separator recognized in READ_ROUTE mode
                 print(f"Warning: Reached end of file in READ_ROUTE mode but no current route info available. Last line number processed: {line_num}. Incomplete final route.", file=sys.stderr)

    # --- Final Output Generation ---
    output_csv_string = "\n".join(output_lines)
    # Add newline at the end if there's content, mimicking typical file writing
    if output_csv_string:
        output_csv_string += "\n"

    log_messages = log_stream.getvalue()

    # Add a summary message to logs
    if not log_messages or "Error" not in log_messages:
         log_messages += f"Processing completed. {len(output_lines)} routes extracted.\n"
         if not output_lines:
             log_messages += "Warning: No route data was extracted.\n"
    else:
         log_messages += f"Processing finished with warnings/errors. {len(output_lines)} routes extracted.\n"

    return output_csv_string, log_messages