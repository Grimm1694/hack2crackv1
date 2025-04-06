from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import google.generativeai as genai
from flask_cors import CORS
import re
import json

# Load environment variables
load_dotenv()
# Initialize Flask app
app = Flask(__name__)
CORS(app)
# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
# Add this after your existing routes but before the app.run() block
@app.route('/api/chat', methods=['POST'])  # Changed endpoint to /api/chat for clarity
def handle_chat():
    try:
        data = request.json
        user_message = data.get('message')
        user_context = data.get('context', {})  # Can include page-specific context

        # Enhanced prompt with page context awareness
        prompt = f"""Act as a maternal care expert assistant. You're helping a user on a {user_context.get('page', 'general')} page.
        User details: {json.dumps(user_context.get('userData', {}))}
        Current message: {user_message}
        
        Respond with:
        - Pregnancy-related advice (1-2 sentences)
        - Emojis where appropriate
        - NEVER give medical diagnosis
        - Format: Markdown without code blocks"""

        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        
        return jsonify({
            "response": response.text,
            "context": user_context  # Return context for continuity
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
def clean_nutrition_values(diet_plan):
    """
    Remove units (g, mg, mcg, etc.) from nutritional values and handle empty strings.
    """
    for day, meals in diet_plan.items():
        for meal, details in meals.items():
            if "nutrition" in details:
                for nutrient, value in details["nutrition"].items():
                    if isinstance(value, str):
                        # Remove non-numeric characters (e.g., 'g', 'mg', 'mcg')
                        cleaned_value = re.sub(r"[^\d.]", "", value)
                        # If the cleaned value is empty, set it to 0
                        details["nutrition"][nutrient] = float(cleaned_value) if cleaned_value else 0
    return diet_plan

def extract_json_from_response(response_text):
    """
    Extract JSON from the Gemini API response, removing any non-JSON text (e.g., Markdown formatting, disclaimers).
    """
    # Remove Markdown formatting (e.g., ```json)
    response_text = response_text.replace("```json", "").replace("```", "").strip()

    # Remove any text after the closing brace of the JSON object
    json_start = response_text.find("{")
    json_end = response_text.rfind("}") + 1
    if json_start == -1 or json_end == 0:
        return None

    # Extract the JSON portion
    json_text = response_text[json_start:json_end]

    # Remove trailing commas
    json_text = re.sub(r",\s*}", "}", json_text)  # Remove trailing commas in objects
    json_text = re.sub(r",\s*]", "]", json_text)  # Remove trailing commas in arrays

    # Parse the JSON
    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        print("Failed to parse JSON:", e)
        print("Problematic JSON:", json_text)  # Print the problematic JSON for debugging
        return None

@app.route('/getDietPlan', methods=['POST'])
def get_diet_plan():
    try:
        # Get user data
        user_data = request.json
        print("Received user data:", user_data)

        # Construct the prompt for Gemini
        prompt = f"""
        Generate a detailed 7-day Indian diet plan for a pregnant woman in JSON format.
        Age: {user_data['age']} years
        Weight: {user_data['weight']} kg
        Height: {user_data['height']} cm
        Gestational Week: {user_data['gestationalWeek']}
        Dietary Preference: {user_data['dietaryPreference']}
        Allergies: {user_data['allergies']}
        State: {user_data.get('state', 'India')}  # Add state for regional cuisine

        The diet plan should include:
        1. A structured 7-day plan with meals for each day.
        2. Each day should include:
           - Pre-Breakfast Snack
           - Breakfast
           - Mid-Morning Snack
           - Lunch
           - Evening Snack
           - Dinner
        3. For each meal, provide:
           - Name of the dish (Indian cuisine, regional if state is provided)
           - Ingredients (brief)
           - Quantity (per serving)
           - Nutritional values (calories, proteins, fats, carbohydrates, vitamins, minerals)
           - Explanation of why this meal is beneficial during pregnancy.
        4. Ensure the plan is rich in iron, calcium, folic acid, and other essential nutrients for pregnancy.
        5. Include traditional Indian dishes and ingredients, with regional variations if state is provided.
        6. Format the output as a JSON object with the following structure:
           {{
             "day1": {{
               "preBreakfastSnack": {{ "name": "...", "ingredients": "...", "quantity": "...", "nutrition": {{...}}, "benefits": "..." }},
               "breakfast": {{ ... }},
               ...
             }},
             "day2": {{ ... }},
             ...
           }}

        **Important Notes:**
        - Do not include units (e.g., g, mg, mcg) in the nutritional values.
        - Ensure all keys and string values are enclosed in double quotes.
        - Do not include trailing commas in JSON objects or arrays.
        - Do not append any additional text (e.g., disclaimers, notes) after the JSON object.
        - For non-vegetarian options, include dishes like chicken curry, fish fry, or egg-based meals.
        - For regional cuisines, include dishes specific to the state (e.g., Hyderabadi biryani for Telangana, Dhokla for Gujarat).
        - You have to generate for all 7 days.
        """

        # Initialize the GenerativeModel
        model = genai.GenerativeModel('gemini-1.5-flash')

        # Generate content
        response = model.generate_content(prompt)

        # Extract the generated text
        diet_plan = response.text
        print("Generated Diet Plan:", diet_plan)

        # Extract JSON from the response
        diet_plan_json = extract_json_from_response(diet_plan)
        if not diet_plan_json:
            return jsonify({"error": "Invalid JSON response from Gemini API"}), 500

        # Clean nutritional values to remove units
        diet_plan_json = clean_nutrition_values(diet_plan_json)

        return jsonify(diet_plan_json)

    except Exception as e:
        print("Error generating diet plan:", str(e))
        return jsonify({"error": "Failed to generate diet plan", "details": str(e)}), 500

if __name__ == '__main__':
    print("Gemini API Key:", os.getenv("GEMINI_API_KEY"))
    app.run(debug=True)