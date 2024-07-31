from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify, session
import plotter

app = Flask(__name__)
app.secret_key = 'secret_key'

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        session['apikey'] = request.form.get('apikey')
        session['packages'] = request.form.get('packages').split(',')
        session['start_date'] = request.form.get('start_date')
        session['end_date'] = request.form.get('end_date')

        if 'confirm' in request.form:
            # Redirect to confirmation page with the form data
            return redirect(url_for('confirmation'))

        elif 'submit' in request.form:
            try:
                plot_file_path = plotter.run(session.get('apikey'), session.get('packages'), session.get('start_date'), session.get('end_date'))
                message = 'Success!'
            except Exception as e:
                message = str(e)
                plot_file_path = None

            return redirect(url_for('result', message=message, plot_file_path=plot_file_path))

    return render_template('index.html')



@app.route('/result', methods=['GET'])
def result():
    message = request.args.get('message')
    plot_file_path = request.args.get('plot_file_path')

    return render_template('result.html', message=message, plot_file_path=plot_file_path)


@app.route('/download', methods=['GET'])
def download():
    plot_file_path = request.args.get('plot_file_path')
    if plot_file_path:
        return send_file(plot_file_path, mimetype='application/zip', as_attachment=True)
    else:
        return "No plot file available."


@app.route('/confirmation', methods=['GET', 'POST'])
def confirmation():
    if request.method == 'POST':

        if 'submit' in request.form:
            print('submit')
            try:
                plot_file_path = plotter.run(session.get('apikey'), session.get('packages'), session.get('start_date'),
                                             session.get('end_date'))
                message = 'Success!'
            except Exception as e:
                message = str(e)
                plot_file_path = None

            return redirect(url_for('result', message=message, plot_file_path=plot_file_path))


    else:
        apikey = session.get('apikey')
        packages = session.get('packages')
        start_date = session.get('start_date')
        end_date = session.get('end_date')
        desired_versions = session.get('desired_versions')

        csv_path = "latest_with-added-date.csv"
        total_apps = 0

        start_date += " 00:00:00.000000"
        end_date += " 00:00:00.000000"

        for package in packages:
            total_apps += plotter.count_apps(package, csv_path, start_date, end_date)


        # Render confirmation page
        return render_template('confirmation.html',
                               apikey=apikey,
                               packages=packages,
                               start_date=start_date,
                               end_date=end_date,
                               desired_versions=desired_versions,
                               version_count=total_apps)



@app.route('/count', methods=['POST'])
def count_apps_ui():

    csv_path = "latest_with-added-date.csv"
    packages = request.form.get('packages').split(',')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')

    start_date += " 00:00:00.000000"
    end_date += " 00:00:00.000000"

    total_apps = 0
    for package in packages:
        total_apps += plotter.count_apps(package, csv_path, start_date, end_date)

    return jsonify({'total_apps': total_apps})


if __name__ == "__main__":
    app.run(debug=False)
