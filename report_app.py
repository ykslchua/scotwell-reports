from flask import Flask, render_template, request, send_file, redirect, url_for
from werkzeug.utils import secure_filename
import os
import pandas as pd
import json
from utils import sanitize_folder_name, allowed_file
from service_report import generate_service_report
from visual_report import generate_visual_report
from utils import (
    load_dropdown_data,
    elaborate_description,
    make_sentence,
    add_timestamp_to_image
)

app = Flask(__name__)
app.config['REPORT_FOLDER'] = 'static/reports'
app.config['UPLOAD_FOLDER'] = 'static/uploads/'

@app.route('/')
def report_selection():
    return render_template('report_selection.html')


@app.route('/service_report', methods=['GET', 'POST'])
def service_report():
    # Load dropdown data and spare parts models from Excel
    company_names, site_addresses_by_company, chargeable_spare_parts, chargeable_module_repair = load_dropdown_data()
    df = pd.read_excel('data/dropdownlist.xlsx')
    
    # Prepare spare part models: { company: { site: { part: [models...] } } }
    spare_parts_models = {}
    for _, row in df.iterrows():
        company = row['Company Name']
        site = row['Site Address']
        if company not in spare_parts_models:
            spare_parts_models[company] = {}
        if site not in spare_parts_models[company]:
            spare_parts_models[company][site] = {}
        for part in df.columns[4:]:
            values = str(row[part]).split(',') if pd.notna(row[part]) else []
            spare_parts_models[company][site][part] = [v.strip() for v in values]

    # Get part types for dropdown
    spare_parts = df.columns[4:].tolist()

    if request.method == 'POST':
    
        screen_condition = request.form['screen_condition']
        action_taken = request.form['action_taken']
        follow_up = request.form.get('follow_up', '')


        # Elaborate using OpenAI
        elaborated_screen_condition = elaborate_description("Screen Condition", screen_condition)
        elaborated_action_taken = elaborate_description("Action Taken", action_taken)
        elaborated_follow_up = elaborate_description("Follow Up", follow_up)
    
    
        # Get form data
        form_data = {
            'company_name': request.form['company_name'],
            'customer_name': request.form['company_name'],  # Assuming customer_name is same as company_name
            'site_address': request.form['site_address'],
            'service_date': request.form['service_date'],
            'screen_condition': elaborated_screen_condition,
            'action_taken': elaborated_action_taken,
            'follow_up': elaborated_follow_up,
            'technician_name': request.form['technician_name'],
            'chargeable_spare_parts': chargeable_spare_parts.get(request.form['site_address'], []),  # Get chargeable spare parts for the selected site address
            'chargeable_module_repair': chargeable_module_repair.get(request.form['site_address'], [])  # Get chargeable module repair for the selected site address
        }

        # Handle multiple file uploads
        # Initialize filename lists
        photo_filenames_before = []
        photo_filenames_after = []

        customer_name = sanitize_folder_name(form_data['customer_name'])
        site_address = sanitize_folder_name(form_data['site_address'])
        service_date = form_data.get('service_date') or datetime.now().strftime("%Y%m%d")

        # Create customer folder if not exists
        customer_folder = os.path.join(app.config['UPLOAD_FOLDER'], customer_name)
        os.makedirs(customer_folder, exist_ok=True)        
        
        # --- BEFORE PHOTOS ---
        if 'photo_before' in request.files:
            photos_before = request.files.getlist('photo_before')
            for i, photo in enumerate(photos_before, start=1):
                if photo and allowed_file(photo.filename):
                    extension = os.path.splitext(photo.filename)[1] or ".jpg"
                    filename = f"{customer_name}_{site_address}_{service_date}_before_{i}{extension}"
                    photo.save(os.path.join(customer_folder, filename))
                    # Add timestamp before saving
                    timestamped_image = add_timestamp_to_image(photo)
                    with open(os.path.join(customer_folder, filename), 'wb') as f:
                        f.write(timestamped_image.read())
                    photo_filenames_before.append(f"{customer_name}/{filename}")

        # --- AFTER PHOTOS ---
        if 'photo_after' in request.files:
            photos_after = request.files.getlist('photo_after')
            for i, photo in enumerate(photos_after, start=1):
                if photo and allowed_file(photo.filename):
                    extension = os.path.splitext(photo.filename)[1] or ".jpg"
                    filename = f"{customer_name}_{site_address}_{service_date}_after_{i}{extension}"
                    photo.save(os.path.join(customer_folder, filename))
                    # Add timestamp before saving
                    timestamped_image = add_timestamp_to_image(photo)
                    with open(os.path.join(customer_folder, filename), 'wb') as f:
                        f.write(timestamped_image.read())
                    photo_filenames_after.append(f"{customer_name}/{filename}")
        
        

        # Generate the service report
        before_paths = [os.path.join(app.config['UPLOAD_FOLDER'], path) for path in photo_filenames_before]
        after_paths = [os.path.join(app.config['UPLOAD_FOLDER'], path) for path in photo_filenames_after]

        filename = generate_service_report(form_data, before_paths, after_paths)


        # Return the template with the generated filename and uploaded photo path
        return render_template(
            'service.html',
            company_names=company_names,
            site_addresses_by_company=site_addresses_by_company,
            spare_parts=spare_parts,
            spare_parts_models_json=json.dumps(spare_parts_models),
            filename=filename,
            photo_filenames_before=photo_filenames_before,
            photo_filenames_after=photo_filenames_after,
            customer_name=form_data['customer_name']
        )


    # Convert spare parts models to JSON for the frontend
    spare_parts_models_json = json.dumps(spare_parts_models)

    return render_template(
        'service.html',
        company_names=company_names,
        site_addresses_by_company=site_addresses_by_company,
        spare_parts=spare_parts,
        spare_parts_models_json=spare_parts_models_json
    )

@app.route('/visual_report', methods=['GET', 'POST'])
def visual_report():
    # Load dropdown data from Excel
    company_names, site_addresses_by_company, chargeable_spare_parts, chargeable_module_repair = load_dropdown_data()
    
    if request.method == 'POST':
        # Get form data for the visual report
        form_data = {
            'company_name': request.form['company_name'],
            'customer_name': request.form['company_name'],
            'site_address': request.form['site_address'],
            'service_date': request.form['service_date'],
            'technician_name': request.form['technician_name'],
            'work_description': make_sentence(request.form['work_description']),
            'visual_inspection': request.form.get('visual_inspection', 'Yes'),
            'faults_reported': request.form.get('faults_reported', 'No')
        }


        # Handle multiple file uploads (for visual reports)
        # Initialize filename lists for before/after photos
        photo_filenames_before = []
        photo_filenames_after = []

        customer_name = sanitize_folder_name(form_data['customer_name'])
        site_address = sanitize_folder_name(form_data['site_address'])
        service_date = form_data.get('service_date') or datetime.now().strftime("%Y%m%d")

        # Create customer folder if not exists
        customer_folder = os.path.join(app.config['UPLOAD_FOLDER'], customer_name)
        os.makedirs(customer_folder, exist_ok=True)        

        # --- BEFORE PHOTOS ---
        if 'photo_before' in request.files:
            photos_before = request.files.getlist('photo_before')
            for i, photo in enumerate(photos_before, start=1):
                if photo and allowed_file(photo.filename):
                    extension = os.path.splitext(photo.filename)[1] or ".jpg"
                    filename = f"{customer_name}_{site_address}_{service_date}_before_{i}{extension}"
                    photo.save(os.path.join(customer_folder, filename))
                    photo_filenames_before.append(f"{customer_name}/{filename}")

        # --- AFTER PHOTOS ---
        if 'photo_after' in request.files:
            photos_after = request.files.getlist('photo_after')
            for i, photo in enumerate(photos_after, start=1):
                if photo and allowed_file(photo.filename):
                    extension = os.path.splitext(photo.filename)[1] or ".jpg"
                    filename = f"{customer_name}_{site_address}_{service_date}_after_{i}{extension}"
                    photo.save(os.path.join(customer_folder, filename))
                    photo_filenames_after.append(f"{customer_name}/{filename}")

        # Generate the visual report
        before_paths = [os.path.join(app.config['UPLOAD_FOLDER'], path) for path in photo_filenames_before]
        after_paths = [os.path.join(app.config['UPLOAD_FOLDER'], path) for path in photo_filenames_after]

        filename = generate_visual_report(form_data, before_paths, after_paths)

        # Return the template with the generated filename and uploaded photo paths
        return render_template(
            'visual.html',
            company_names=company_names,
            site_addresses_by_company=site_addresses_by_company,
            filename=filename,
            photo_filenames_before=photo_filenames_before,
            photo_filenames_after=photo_filenames_after,
            customer_name=form_data['customer_name']
        )

    # Return the template for GET request
    return render_template(
        'visual.html',
        company_names=company_names,
        site_addresses_by_company=site_addresses_by_company
    )


@app.route('/download/<filename>')
def download_file(filename):
    # Serve the generated file for download
    return send_from_directory('static', filename)
    
    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
