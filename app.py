from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import pandas as pd
from matching import match_donor, load_data
from twilio.rest import Client
import math
import logging
import secrets
import time
import re
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import jwt

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Twilio credentials
TWILIO_SID = os.getenv('TWILIO_SID', 'ACe550a7d3d9a84f08982c094145a4ed39')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '4486564aaf275048dbd5764f68fa1208')
TWILIO_PHONE = os.getenv('TWILIO_PHONE', '+919692906282')
TWILIO_TRIAL_MODE = True

# JWT secret for hospital authentication
JWT_SECRET = os.getenv('JWT_SECRET', 'your-secret-key')

# Initialize Twilio client
try:
    twilio_client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
except Exception as e:
    logging.error(f"Failed to initialize Twilio client: {e}")
    twilio_client = None

# Load data
donors, _, hospitals = load_data()

# Initialize appointments.csv if it doesn't exist
APPOINTMENTS_FILE = 'appointments.csv'
if not os.path.exists(APPOINTMENTS_FILE):
    pd.DataFrame(columns=['id', 'donor_id', 'recipient_location', 'appointment_date', 'notes', 'status']).to_csv(APPOINTMENTS_FILE, index=False)

# Odisha location mapping
ODISHA_LOCATIONS = {
    'Bhubaneswar': (20.2961, 85.8245),
    'Cuttack': (20.4625, 85.8828),
    'Rourkela': (22.2604, 84.8536),
    'Berhampur': (19.3140, 84.7941),
    'Sambalpur': (21.4669, 83.9757),
    'Puri': (19.8134, 85.8315),
    'Balasore': (21.4940, 86.9427),
    'Bargarh': (21.3353, 83.6161),
    'Angul': (20.8442, 85.1511),
    'Jharsuguda': (21.8553, 84.0062),
    'Dhenkanal': (20.6587, 85.5980),
    'Kendrapara': (20.5002, 86.4166),
    'Jagatsinghpur': (20.2548, 86.1706),
    'Koraput': (18.8110, 82.7105),
    'Rayagada': (19.1711, 83.4160),
    'Bolangir': (20.7074, 83.4843),
    'Sundargarh': (22.1167, 84.0333),
    'Nayagarh': (20.1281, 85.0985),
    'Malkangiri': (18.3650, 82.1367),
    'Khordha': (20.1883, 85.6214)
}

# Temporary storage for phone reveal tokens
phone_tokens = {}

# Registered hospitals (for demo; in production, use a database)
REGISTERED_HOSPITALS = {
    'hospital1': 'password123'
}

def mask_phone(phone):
    """Mask a phone number, showing only the last 4 digits."""
    try:
        phone_str = str(phone).replace('+', '').replace('-', '').replace(' ', '')
        if not phone_str or len(phone_str) < 4:
            return "Unknown"
        return f"XXXX-XXX-{phone_str[-4:]}"
    except Exception as e:
        logging.error(f"Error masking phone number {phone}: {e}")
        return "Unknown"

def validate_phone_number(phone):
    """Validate phone number in E.164 format."""
    if not phone:
        return False
    phone_str = str(phone)
    pattern = r'^\+[1-9]\d{9,14}$'
    return bool(re.match(pattern, phone_str))

def calculate_availability(last_donation):
    """Calculate donor availability based on last donation (56-day rule)."""
    try:
        if pd.isna(last_donation):
            return {"status": "Available", "available_date": None}
        last_donation_date = pd.to_datetime(last_donation)
        available_date = last_donation_date + timedelta(days=56)
        if datetime.now() >= available_date:
            return {"status": "Available", "available_date": None}
        return {"status": f"Unavailable until {available_date.strftime('%Y-%m-%d')}", "available_date": available_date.strftime('%Y-%m-%d')}
    except Exception as e:
        logging.error(f"Error calculating availability for {last_donation}: {e}")
        return {"status": "Available", "available_date": None}

def verify_jwt(token):
    """Verify JWT token for hospital authentication."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload['hospital_id']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')

@app.route('/donors')
def donors():
    """Serve the donors page."""
    return render_template('donors.html')

@app.route('/hospital_inventory')
def hospital_inventory():
    """Serve the hospital inventory page."""
    return render_template('hospital_inventory.html')

@app.route('/hospital/login', methods=['POST'])
def hospital_login():
    """Authenticate hospital and issue JWT token."""
    try:
        data = request.json
        hospital_id = data.get('hospital_id')
        password = data.get('password')
        
        if not hospital_id or not password:
            return jsonify({'status': 'error', 'message': 'Missing hospital_id or password.'}), 400
        
        if hospital_id in REGISTERED_HOSPITALS and REGISTERED_HOSPITALS[hospital_id] == password:
            token = jwt.encode({
                'hospital_id': hospital_id,
                'exp': datetime.utcnow() + timedelta(hours=24)
            }, JWT_SECRET, algorithm='HS256')
            return jsonify({'status': 'success', 'token': token})
        else:
            return jsonify({'status': 'error', 'message': 'Invalid credentials.'}), 401
    except Exception as e:
        logging.error(f"Error in /hospital/login: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/hospital/update', methods=['POST'])
def hospital_update():
    """Update hospital inventory and broadcast to clients."""
    try:
        token = request.headers.get('Authorization')
        if not token or not token.startswith('Bearer '):
            return jsonify({'status': 'error', 'message': 'Missing or invalid token.'}), 401
        
        token = token.split(' ')[1]
        hospital_id = verify_jwt(token)
        if not hospital_id:
            return jsonify({'status': 'error', 'message': 'Invalid or expired token.'}), 401
        
        data = request.json
        name = data.get('name')
        blood_type = data.get('blood_type')
        stock = data.get('stock')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        if not all([name, blood_type, stock is not None, latitude, longitude]):
            return jsonify({'status': 'error', 'message': 'Missing required fields.'}), 400
        
        if blood_type not in ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+']:
            return jsonify({'status': 'error', 'message': 'Invalid blood type.'}), 400
        
        global hospitals
        hospitals = pd.read_csv('hospitals.csv')
        hospital_index = hospitals[(hospitals['name'] == name) & (hospitals['blood_type'] == blood_type)].index
        
        if not hospital_index.empty:
            hospitals.loc[hospital_index, 'stock'] = stock
            hospitals.loc[hospital_index, 'latitude'] = latitude
            hospitals.loc[hospital_index, 'longitude'] = longitude
        else:
            new_id = hospitals['id'].max() + 1 if not hospitals.empty else 1
            new_hospital = pd.DataFrame([{
                'id': new_id,
                'name': name,
                'latitude': latitude,
                'longitude': longitude,
                'blood_type': blood_type,
                'stock': stock
            }])
            hospitals = pd.concat([hospitals, new_hospital], ignore_index=True)
        
        hospitals.to_csv('hospitals.csv', index=False)
        
        # Broadcast update to all connected clients
        socketio.emit('hospital_update', {
            'name': name,
            'blood_type': blood_type,
            'stock': stock,
            'latitude': latitude,
            'longitude': longitude
        })
        
        return jsonify({'status': 'success', 'message': 'Hospital data updated.'})
    except Exception as e:
        logging.error(f"Error in /hospital/update: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/match', methods=['POST'])
def match():
    """API endpoint to match donors to a recipient using AI."""
    try:
        data = request.json
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided.'}), 400
        
        location = data.get('location')
        if location not in ODISHA_LOCATIONS:
            return jsonify({'status': 'error', 'message': 'Invalid location.'}), 400
        
        latitude, longitude = ODISHA_LOCATIONS[location]
        try:
            urgency = int(data.get('urgency', 0))
        except (ValueError, TypeError):
            return jsonify({'status': 'error', 'message': 'Urgency must be an integer between 1 and 10.'}), 400
        
        recipient = {
            'blood_type': data.get('blood_type'),
            'latitude': latitude,
            'longitude': longitude,
            'urgency': urgency
        }
        
        if not recipient['blood_type'] or recipient['blood_type'] not in ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+']:
            return jsonify({'status': 'error', 'message': 'Invalid blood type.'}), 400
        if urgency < 1 or urgency > 10:
            return jsonify({'status': 'error', 'message': 'Urgency must be between 1 and 10.'}), 400
        
        logging.debug(f"Recipient data: {recipient}")
        
        matches = match_donor(recipient, donors, hospitals)
        
        for match in matches:
            if math.isinf(match['hospital_distance']) or match['hospital_distance'] > 1000:
                match['hospital_distance'] = None
            match['masked_phone'] = mask_phone(match.get('phone'))
            token = secrets.token_hex(16)
            phone_tokens[token] = {
                'phone': match.get('phone', 'Unknown'),
                'expires': time.time() + 300
            }
            match['contact_token'] = token
            # Add availability status
            donor = donors[donors['id'] == match['donor_id']].iloc[0]
            availability = calculate_availability(donor['last_donation'])
            match['availability_status'] = availability['status']
            match['last_donation'] = donor['last_donation']
        
        closest_hospital = None
        min_distance = float('inf')
        for _, hospital in hospitals.iterrows():
            hospital_loc = (hospital['latitude'], hospital['longitude'])
            recipient_loc = (recipient['latitude'], recipient['longitude'])
            distance = haversine(hospital_loc, recipient_loc)
            if distance < min_distance:
                min_distance = distance
                closest_hospital = hospital
        
        sms_status = "not_attempted"
        if matches and twilio_client:
            closest_donor_id = matches[0]['donor_id']
            donor = donors[donors['id'] == closest_donor_id].iloc[0]
            to_phone = donor['phone']
            
            if not validate_phone_number(to_phone):
                sms_status = f"failed: Invalid phone number format: {to_phone}"
                logging.error(sms_status)
            elif to_phone == TWILIO_PHONE:
                sms_status = "failed: To and From numbers cannot be the same"
                logging.error(sms_status)
            elif TWILIO_TRIAL_MODE:
                sms_status = "mocked: trial mode"
                logging.info(f"Mocked SMS to {to_phone}")
            else:
                hospital_contact = closest_hospital['name'] if closest_hospital is not None else "local hospital"
                message = f"Urgent: {recipient['blood_type']} blood needed in {location}. Contact {hospital_contact} at +919876543210."
                try:
                    twilio_client.messages.create(
                        body=message,
                        from_=TWILIO_PHONE,
                        to=to_phone
                    )
                    sms_status = "sent"
                    logging.info(f"SMS sent to {to_phone}")
                except Exception as sms_error:
                    sms_status = f"failed: {sms_error}"
                    logging.error(f"Failed to send SMS: {sms_status}")
        
        return jsonify({
            'status': 'success',
            'matches': matches,
            'sms_status': sms_status
        })
    
    except Exception as e:
        logging.error(f"Error in /match: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/hospitals', methods=['GET'])
def get_hospitals():
    """Return hospital data."""
    try:
        hospital_data = hospitals.to_dict(orient='records')
        return jsonify({'status': 'success', 'hospitals': hospital_data})
    except Exception as e:
        logging.error(f"Error in /hospitals: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/reveal_phone', methods=['POST'])
def reveal_phone():
    """Reveal phone number using a one-time token."""
    try:
        data = request.json
        token = data.get('token')
        if not token or token not in phone_tokens:
            return jsonify({'status': 'error', 'message': 'Invalid or expired token.'}), 400
        
        token_data = phone_tokens[token]
        if time.time() > token_data['expires']:
            del phone_tokens[token]
            return jsonify({'status': 'error', 'message': 'Token has expired.'}), 400
        
        phone = token_data['phone']
        del phone_tokens[token]
        
        return jsonify({'status': 'success', 'phone': phone})
    
    except Exception as e:
        logging.error(f"Error in /reveal_phone: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/schedule_appointment', methods=['POST'])
def schedule_appointment():
    """Schedule a donation appointment."""
    try:
        data = request.json
        donor_id = data.get('donor_id')
        recipient_location = data.get('recipient_location')
        appointment_date = data.get('appointment_date')
        notes = data.get('notes', '')
        
        if not all([donor_id, recipient_location, appointment_date]):
            return jsonify({'status': 'error', 'message': 'Missing required fields.'}), 400
        
        if recipient_location not in ODISHA_LOCATIONS:
            return jsonify({'status': 'error', 'message': 'Invalid location.'}), 400
        
        donor = donors[donors['id'] == donor_id]
        if donor.empty:
            return jsonify({'status': 'error', 'message': 'Donor not found.'}), 400
        donor = donor.iloc[0]
        
        try:
            appt_datetime = datetime.strptime(appointment_date, '%Y-%m-%d %H:%M')
            if appt_datetime < datetime.now():
                return jsonify({'status': 'error', 'message': 'Appointment date must be in the future.'}), 400
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Invalid date format. Use YYYY-MM-DD HH:MM.'}), 400
        
        availability = calculate_availability(donor['last_donation'])
        if 'Unavailable' in availability['status']:
            return jsonify({'status': 'error', 'message': f"Donor is {availability['status']}."}), 400
        
        appointments = pd.read_csv(APPOINTMENTS_FILE)
        new_id = appointments['id'].max() + 1 if not appointments.empty else 1
        new_appointment = pd.DataFrame([{
            'id': new_id,
            'donor_id': donor_id,
            'recipient_location': recipient_location,
            'appointment_date': appointment_date,
            'notes': notes,
            'status': 'Pending'
        }])
        
        appointments = pd.concat([appointments, new_appointment], ignore_index=True)
        appointments.to_csv(APPOINTMENTS_FILE, index=False)
        
        sms_status = "not_attempted"
        if twilio_client:
            to_phone = donor['phone']
            if not validate_phone_number(to_phone):
                sms_status = f"failed: Invalid phone number format: {to_phone}"
                logging.error(sms_status)
            elif to_phone == TWILIO_PHONE:
                sms_status = "failed: To and From numbers cannot be the same"
                logging.error(sms_status)
            elif TWILIO_TRIAL_MODE:
                sms_status = "mocked: trial mode"
                logging.info(f"Mocked appointment SMS to {to_phone}")
            else:
                message = f"Donation appointment scheduled on {appointment_date} in {recipient_location}. Notes: {notes}"
                try:
                    twilio_client.messages.create(
                        body=message,
                        from_=TWILIO_PHONE,
                        to=to_phone
                    )
                    sms_status = "sent"
                    logging.info(f"Appointment SMS sent to {to_phone}")
                except Exception as sms_error:
                    sms_status = f"failed: {sms_error}"
                    logging.error(f"Failed to send appointment SMS: {sms_status}")
        
        return jsonify({
            'status': 'success',
            'appointment': new_appointment.to_dict(orient='records')[0],
            'sms_status': sms_status
        })
    
    except Exception as e:
        logging.error(f"Error in /schedule_appointment: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/donation_history', methods=['POST'])
def donation_history():
    """Return donation history for a donor."""
    try:
        data = request.json
        donor_id = data.get('donor_id')
        if not donor_id:
            return jsonify({'status': 'error', 'message': 'Donor ID required.'}), 400
        
        donor = donors[donors['id'] == donor_id]
        if donor.empty:
            return jsonify({'status': 'error', 'message': 'Donor not found.'}), 400
        donor = donor.iloc[0]
        
        appointments = pd.read_csv(APPOINTMENTS_FILE)
        donor_appointments = appointments[
            (appointments['donor_id'] == donor_id) & 
            (appointments['status'] == 'Completed')
        ]
        
        history = []
        if not pd.isna(donor['last_donation']):
            history.append(donor['last_donation'])
        history.extend(donor_appointments['appointment_date'].apply(
            lambda x: datetime.strptime(x, '%Y-%m-%d %H:%M').strftime('%Y-%m-%d')
        ).tolist())
        
        return jsonify({
            'status': 'success',
            'donor_id': donor_id,
            'history': sorted(history)
        })
    
    except Exception as e:
        logging.error(f"Error in /donation_history: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def haversine(loc1, loc2):
    """Calculate distance between two locations."""
    from haversine import haversine
    return haversine(loc1, loc2)

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection."""
    logging.info("Client connected to WebSocket")
    emit('connection_status', {'status': 'connected'})

if __name__ == "__main__":
    # Run Flask's built-in server for development only
    app.run(debug=True, host='0.0.0.0', port=5000)
