
# JANUS (Beginner Version)
# See APK endpoints evolution over time

![Sponsors](./sponsors.png)

This Flask web app allows you to analyse a chronological series of APK files, extract subdomains, domains, and URLs, and visualise their presence across different versions of Android apps. It uses the AndroZoo research dataset and several Python libraries (such as Androguard) to download, process, and visualise the data.

If you are not familiar with git or running python code, we have included an additional tutorial guide inside the repository. Please click here to view.


![Janus UI](./janus.png)


## Features

- Download a chronological sequence of APK files from AndroZoo for a given date range.
- Extract subdomains, domains, and URLs from APK files
- Analyze and visualise the extracted data
- Provide heatmaps and grouped bar charts for the extracted data

## Prerequisites

Ensure you have met the following requirements:

- Python 3.7 or higher
- Access to the AndroZoo dataset (API key required)

## Installation

1. **Clone the repository:**
```
   git clone https://github.com/digisilk/janus_beginner.git
   cd janus_beginner
```
2. **Create a virtual environment:**
```
   python3 -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```
3. **Install the required dependencies:**
```
   pip install -r requirements.txt
```
## Configuration

### API Key:

Obtain an API key from AndroZoo (https://androzoo.uni.lu). Set the API key in the index.html form if you wish it to be used by default.

### CSV File:

Ensure the AndroZoo database (latest_with-added-date.csv file) from AndroZoo is available in the project directory. The script will download and extract this file if it does not exist.

## Running the App

### Start the Flask application:
```
   python app.py
```
### Access the application:

Open your web browser and go to http://127.0.0.1:5000.

## Usage

### Enter the required details:

- API key
- Package names (comma-separated)
- Start date (YYYY-MM-DD)
- End date (YYYY-MM-DD)

### Submit the form:

- Click on the 'Confirm' button to see a summary of the apps to be processed.
- Click on the 'Submit' button to start the analysis and visualization process.

### Download the results:

After the process is completed, a link to download the results as a zip file will be provided.

## File Structure

```
.
├── app.py                   # Main Flask application
├── plotter.py               # Script containing processing and plotting functions
├── templates
│   ├── index.html           # Main page template
│   ├── confirmation.html    # Confirmation page template
│   ├── result.html          # Result page template
├── latest_with-added-date.csv  # AndroZoo dataset CSV file
├── requirements.txt         # Python dependencies
├── README.md                # This readme file

```

## Dependencies

```
- Flask
- Pandas
- Plotly
- Requests
- Androguard
- tldextract
- tqdm
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the [TBC] License.

## Acknowledgements

- AndroZoo for providing the dataset.
- Androguard for the reverse engineering framework.
- Flask for the web framework.
- Plotly for data visualisation.
