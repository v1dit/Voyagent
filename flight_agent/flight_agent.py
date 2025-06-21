diff --git a/flight_agent/flight_agent.py b/flight_agent/flight_agent.py
index 609c92ebedbe303546586e118e05b1276c9b5fef..d8027147382570cd71456a4d44d4ba22b2233e62 100644
--- a/flight_agent/flight_agent.py
+++ b/flight_agent/flight_agent.py
@@ -1,39 +1,41 @@
 import requests
 import os
 import re
 from dotenv import load_dotenv
 from datetime import datetime
 import logging
+import time
 
 # Configure logging
 logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
 logger = logging.getLogger('flight_agent')
 
 # Load environment variables
 load_dotenv()
 RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
+FLYSCRAPER_HOST = os.getenv("FLYSCRAPER_HOST", "flyscraper.p.rapidapi.com")
 
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
diff --git a/flight_agent/flight_agent.py b/flight_agent/flight_agent.py
index 609c92ebedbe303546586e118e05b1276c9b5fef..d8027147382570cd71456a4d44d4ba22b2233e62 100644
--- a/flight_agent/flight_agent.py
+++ b/flight_agent/flight_agent.py
@@ -93,86 +95,98 @@ class FlightAgent:
                 
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
 
-        url = "https://flyscraper.p.rapidapi.com/flight/search"
+        url = f"https://{FLYSCRAPER_HOST}/flight/search"
         headers = {
             "X-RapidAPI-Key": self.api_key,
-            "X-RapidAPI-Host": "flyscraper.p.rapidapi.com"
+            "X-RapidAPI-Host": FLYSCRAPER_HOST,
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
-            "sort": "best"  # Default to best flights
+            "sort": "best",  # Default to best flights
         }
+        if return_date:
+            params["returnDate"] = return_date
 
         logger.info(f"Searching flights: {origin_sky_id} -> {dest_sky_id} on {departure_formatted}")
         
         try:
             response = requests.get(url, headers=headers, params=params)
             logger.info(f"API request URL: {response.url}")
             response.raise_for_status()
-            
+
             data = response.json()
-            
-            # Check if we need to handle incomplete results
-            if data.get("data", {}).get("context", {}).get("status") == "incomplete":
-                # In a real implementation, you'd call the /flight/search-incomplete endpoint
-                # until the status is 'complete', but for simplicity we'll just return what we have
-                logger.warning("Received incomplete results. In production, should poll until complete.")
-            
-            # Process the flight results to extract useful information
+
+            status = data.get("data", {}).get("context", {}).get("status")
+            if status == "incomplete":
+                # Poll the incomplete endpoint until results are ready or timeout
+                session_id = data.get("data", {}).get("context", {}).get("sessionId")
+                polling_url = data.get("data", {}).get("context", {}).get("pollingUrl")
+                if polling_url and session_id:
+                    for _ in range(5):
+                        time.sleep(1)
+                        poll_resp = requests.get(polling_url, headers=headers, params={"sessionId": session_id})
+                        poll_resp.raise_for_status()
+                        data = poll_resp.json()
+                        status = data.get("data", {}).get("context", {}).get("status")
+                        if status == "complete":
+                            break
+                else:
+                    logger.warning("Incomplete results but no polling info provided")
+
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
