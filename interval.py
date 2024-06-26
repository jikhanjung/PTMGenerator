import os
from datetime import datetime

def detect_irregular_intervals(directory_path):
    """
    Detects image files with irregular time intervals in a directory, 
    first determining the typical interval from existing images.

    Args:
        directory_path (str): The path to the directory containing the images.

    Returns:
        list: A list of tuples (filename, actual_interval) for images with irregular intervals.
    """
    def get_file_creation_time(filename):
        """Helper function to get file creation time for sorting."""
        filepath = os.path.join(directory_path, filename)
        return os.path.getctime(filepath)

    image_files = [f for f in os.listdir(directory_path) if f.endswith(('.jpg', '.jpeg', '.png', '.tiff'))]
    # Sort files by creation time using the helper function
    image_files.sort(key=get_file_creation_time) 

    intervals = []
    for i in range(1, len(image_files)):
        try:
            filepath1 = os.path.join(directory_path, image_files[i - 1])
            filepath2 = os.path.join(directory_path, image_files[i])
            ctime1 = os.path.getctime(filepath1)
            ctime2 = os.path.getctime(filepath2)
            datetime1 = datetime.fromtimestamp(ctime1)
            datetime2 = datetime.fromtimestamp(ctime2)

            actual_interval = round((datetime2 - datetime1).total_seconds())
            intervals.append(actual_interval)
        except FileNotFoundError:
            print(f"Error: Image file not found: {image_files[i]}")

    # Determine the most common interval (typical_interval)
    print(intervals)
    interval_counts = {}
    for interval in intervals:
        interval_counts[interval] = interval_counts.get(interval, 0) + 1
    typical_interval = max(interval_counts, key=interval_counts.get)  # Most frequent interval

    irregular_intervals = []
    for interval in intervals:
        print(interval)
        if not (0.5 * typical_interval <= actual_interval <= 1.5 * typical_interval):
            if actual_interval > 1.5 * typical_interval:
                irregular_intervals.append((image_files[i], actual_interval))

    return image_files, typical_interval, irregular_intervals

# Example usage
directory_path = "C:/Users/Jikhan Jung/Desktop/new_folder"  # Replace with your actual directory path
typical_interval, irregular_images = detect_irregular_intervals(directory_path)

if irregular_images:
    print("Images with irregular time intervals:")
    for filename, interval in irregular_images:
        print(f"{filename}: {interval} seconds (typical interval: {typical_interval} seconds)")
else:
    print("No images with irregular time intervals found.")
