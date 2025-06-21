import requests
import os
import re
from dotenv import load_dotenv
from datetime import datetime
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('flight_agent')

# Load environment variables
load_dotenv()
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
FLYSCRAPER_HOST = os.getenv("FLYSCRAPER_HOST", "flyscraper.p.rapidapi.com")

class FlightAgent:
    def __init__(self):
        self.api_key = RAPIDAPI_KEY
        if not self.api_key:
            logger.warning("RAPIDAPI_KEY is not set. API calls will fail.")
        
        # Store SkyID mappings - these would need to be populated with actual values
        # from /get-config endpoint in a production system
        self.sky_id_map = {
            "new york": "NYCA",
            "los angeles": "LAXA",
            "chicago": "CHIA",
            "houston": "HOUA",
            "dallas": "DFWA",
            "phoenix": "PHXA",
            "san antonio": "SATA",
            "san diego": "SANA",
            "san francisco": "SFOA",
            "austin": "AUSA",
            "seattle": "SEAA",
            "denver": "DENA",
            "washington": "WASA",
            "boston": "BOSA",
            "miami": "MIAA",
            "atlanta": "ATLA",
            "las vegas": "LASA",
            "philadelphia": "PHLA",
            "detroit": "DETA",
            "portland": "PDXA",
            "paris": "PARI"  # Example from API docs
        }
        
    def _get_sky_id(self, city):
        """
        Convert city name to SkyScanner skyId format
        """
        city = city.lower()
        return self.sky_id_map.get(city, city.upper() + "A")  # Fallback format

    def extract_flight_details(self, query):
        """
        Extract flight details from natural language query
        """
        origin_match = re.search(r'from\s+([A-Za-z\s]+?)\s+to', query)
        dest_match = re.search(r'to\s+([A-Za-z\s]+?)(?:\s|\.|$)', query)
        
        # More complex date patterns
        date_match = re.search(r'from\s+(\w+)\s+(\d+)(?:st|nd|rd|th)?\s+to\s+(\w+)\s+(\d+)(?:st|nd|rd|th)?', query, re.IGNORECASE)
        if not date_match:
            date_match = re.search(r'(\w+)\s+(\d+)(?:st|nd|rd|th)?\s+to\s+(\w+)\s+(\d+)(?:st|nd|rd|th)?', query, re.IGNORECASE)
        
        budget_match = re.search(r'budget\s+(?:is\s+|of\s+)?[$]?(\d+)', query)
        people_match = re.search(r'(\d+)\s+(?:people|persons|passengers)', query)

        origin = origin_match.group(1).strip() if origin_match else ""
        destination = dest_match.group(1).strip() if dest_match else ""

        current_year = datetime.now().year
        depart = return_ = None
        if date_match:
            try:
                depart_month = datetime.strptime(date_match.group(1), '%B').month
            except ValueError:
                # Try abbreviated month name
                try:
                    depart_month = datetime.strptime(date_match.group(1), '%b').month
                except ValueError:
                    depart_month = None
                    
            try:
                return_month = datetime.strptime(date_match.group(3), '%B').month
            except ValueError:
                # Try abbreviated month name
                try:
                    return_month = datetime.strptime(date_match.group(3), '%b').month
                except ValueError:
                    return_month = None
                
            if depart_month and return_month:
                depart = f"{current_year}-{depart_month:02d}-{int(date_match.group(2)):02d}"
                return_ = f"{current_year}-{return_month:02d}-{int(date_match.group(4)):02d}"

        budget = float(budget_match.group(1)) if budget_match else None
        passengers = int(people_match.group(1)) if people_match else 1

        return {
            "origin": origin,
            "destination": destination,
            "departure_date": depart,
            "return_date": return_,
            "budget": budget,
            "passengers": passengers,
            "flight_budget": 0.4 * budget if budget else None
        }

    def get_flights(self, origin, destination, departure_date, return_date=None, passengers=1):
        """
        Search for flights using the Fly Scraper API with proper parameters
        """
        origin_sky_id = self._get_sky_id(origin)
        dest_sky_id = self._get_sky_id(destination)

        url = f"https://{FLYSCRAPER_HOST}/flight/search"
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": FLYSCRAPER_HOST,
        }
        
        # Format date as required by API (YYYY-MM-DD)
        departure_formatted = departure_date
        
        # Set up query parameters according to API documentation
        params = {
            "originSkyId": origin_sky_id,
            "destinationSkyId": dest_sky_id,
            "departureDate": departure_formatted,
            "adults": passengers,
            "cabinClass": "economy",
            "currency": "USD",
            "sort": "best",  # Default to best flights
        }
        if return_date:
            params["returnDate"] = return_date

        logger.info(f"Searching flights: {origin_sky_id} -> {dest_sky_id} on {departure_formatted}")
        
        try:
            response = requests.get(url, headers=headers, params=params)
            logger.info(f"API request URL: {response.url}")
            response.raise_for_status()

            data = response.json()

            status = data.get("data", {}).get("context", {}).get("status")
            if status == "incomplete":
                # Poll the incomplete endpoint until results are ready or timeout
                session_id = data.get("data", {}).get("context", {}).get("sessionId")
                polling_url = data.get("data", {}).get("context", {}).get("pollingUrl")
                if polling_url and session_id:
                    for _ in range(5):
                        time.sleep(1)
                        poll_resp = requests.get(polling_url, headers=headers, params={"sessionId": session_id})
                        poll_resp.raise_for_status()
                        data = poll_resp.json()
                        status = data.get("data", {}).get("context", {}).get("status")
                        if status == "complete":
                            break
                else:
                    logger.warning("Incomplete results but no polling info provided")

            return self._process_flight_results(data, return_date)
        except Exception as e:
            logger.error(f"Error getting flights: {str(e)}")
            return {"error": str(e)}

    def _process_flight_results(self, api_response, return_date=None):
        """
        Process and simplify the flight API response
        """
        try:
            # Check if we have itineraries
            itineraries = api_response.get("data", {}).get("itineraries", [])
            
            if not itineraries:
                return {"data": [], "count": 0, "message": "No flights found"}
            
            processed_flights = []
            
            # Extract relevant flight information
            for itinerary in itineraries[:10]:  # Limit to top 10 flights
                legs = itinerary.get("legs", [])
                if not legs:
                    continue
                
                # Get first leg details
                leg = legs[0]
                
                # Extract price
                price_info = itinerary.get("pricing", {}).get("pricingOptions", [{}])[0]
                price = price_info.get("price", {}).get("amount", "N/A")
                
                # Extract airline info
                carriers = leg.get("carriers", {})
                marketing = carriers.get("marketing", [{}])[0]
                airline_name = marketing.get("name", "Unknown Airline")
                flight_number = marketing.get("flightNumber", "")
                
                # Extract times
                departure_time = leg.get("departure", {}).get("time", "")
                arrival_time = leg.get("arrival", {}).get("time", "")
                
                # Extract stops
                stop_count = leg.get("stopCount", 0)
                duration = leg.get("durationInMinutes", 0)
                
                processed_flight = {
                    "airline": airline_name,
                    "flightNumber": flight_number,
                    "price": price,
                    "departureTime": departure_time,
                    "arrivalTime": arrival_time,
                    "stops": stop_count,
                    "duration": duration,
                    "itineraryId": itinerary.get("id", "")
                }
                
                processed_flights.append(processed_flight)
            
            return {
                "data": processed_flights,
                "count": len(processed_flights)
            }
            
        except Exception as e:
            logger.error(f"Error processing flight results: {str(e)}")
            return {"data": [], "count": 0, "error": str(e)}

    def get_flight_recommendations(self, user_query):
        """
        Main function to extract details from query and get flight recommendations
        """
        details = self.extract_flight_details(user_query)
        logger.info(f"Extracted details: {details}")

        if not all([details['origin'], details['destination'], details['departure_date']]):
            return {"error": "Missing critical info (origin, destination, or date) in query.", "details": details}

        result = self.get_flights(
            details["origin"],
            details["destination"],
            details["departure_date"],
            details["return_date"],
            details["passengers"]
        )

        return {**result, "extracted": details}


# Example usage
if __name__ == "__main__":
    agent = FlightAgent()
    result = agent.get_flight_recommendations(
        "plan me a 3 day trip to Dallas, Texas from New York from July 10th to July 13th, 2025. Budget is 500 for 2 people"
    )
    print(result)
