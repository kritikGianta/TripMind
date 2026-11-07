"""Reference data for the demo dataset.

Airport codes, names, coordinates and timezones, and city centre coordinates, are public reference
facts (coordinates rounded). Everything the generator builds on top of them (airlines, schedules,
fares, hotels, rooms) is synthetic and labelled as such in the product.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CityKind = Literal["metro", "heritage", "beach", "hill", "spiritual", "international"]


@dataclass(frozen=True)
class AirportRef:
    code: str
    name: str
    city: str
    country: str
    latitude: float
    longitude: float
    timezone: str


@dataclass(frozen=True)
class CityRef:
    name: str
    country: str
    latitude: float
    longitude: float
    currency: str
    kind: CityKind
    tier: int  # 1 = largest market; drives hotel count and price level
    airports: tuple[str, ...]


AIRPORTS: tuple[AirportRef, ...] = (
    AirportRef(
        "DEL",
        "Indira Gandhi International Airport",
        "Delhi",
        "IN",
        28.5562,
        77.1000,
        "Asia/Kolkata",
    ),
    AirportRef(
        "BOM",
        "Chhatrapati Shivaji Maharaj International Airport",
        "Mumbai",
        "IN",
        19.0896,
        72.8656,
        "Asia/Kolkata",
    ),
    AirportRef(
        "BLR",
        "Kempegowda International Airport",
        "Bengaluru",
        "IN",
        13.1986,
        77.7066,
        "Asia/Kolkata",
    ),
    AirportRef(
        "MAA", "Chennai International Airport", "Chennai", "IN", 12.9941, 80.1709, "Asia/Kolkata"
    ),
    AirportRef(
        "CCU",
        "Netaji Subhas Chandra Bose International Airport",
        "Kolkata",
        "IN",
        22.6547,
        88.4467,
        "Asia/Kolkata",
    ),
    AirportRef(
        "HYD",
        "Rajiv Gandhi International Airport",
        "Hyderabad",
        "IN",
        17.2403,
        78.4294,
        "Asia/Kolkata",
    ),
    AirportRef("GOI", "Dabolim Airport", "Goa", "IN", 15.3808, 73.8314, "Asia/Kolkata"),
    AirportRef(
        "COK", "Cochin International Airport", "Kochi", "IN", 10.1520, 76.4019, "Asia/Kolkata"
    ),
    AirportRef(
        "JAI", "Jaipur International Airport", "Jaipur", "IN", 26.8242, 75.8122, "Asia/Kolkata"
    ),
    AirportRef(
        "AMD",
        "Sardar Vallabhbhai Patel International Airport",
        "Ahmedabad",
        "IN",
        23.0772,
        72.6347,
        "Asia/Kolkata",
    ),
    AirportRef("PNQ", "Pune Airport", "Pune", "IN", 18.5821, 73.9197, "Asia/Kolkata"),
    AirportRef(
        "LKO",
        "Chaudhary Charan Singh International Airport",
        "Lucknow",
        "IN",
        26.7606,
        80.8893,
        "Asia/Kolkata",
    ),
    AirportRef(
        "ATQ",
        "Sri Guru Ram Dass Jee International Airport",
        "Amritsar",
        "IN",
        31.7096,
        74.7973,
        "Asia/Kolkata",
    ),
    AirportRef(
        "VNS",
        "Lal Bahadur Shastri International Airport",
        "Varanasi",
        "IN",
        25.4524,
        82.8593,
        "Asia/Kolkata",
    ),
    AirportRef(
        "SXR",
        "Sheikh ul-Alam International Airport",
        "Srinagar",
        "IN",
        33.9871,
        74.7742,
        "Asia/Kolkata",
    ),
    AirportRef(
        "IXZ",
        "Veer Savarkar International Airport",
        "Port Blair",
        "IN",
        11.6412,
        92.7297,
        "Asia/Kolkata",
    ),
    AirportRef(
        "TRV",
        "Thiruvananthapuram International Airport",
        "Thiruvananthapuram",
        "IN",
        8.4821,
        76.9201,
        "Asia/Kolkata",
    ),
    AirportRef("UDR", "Maharana Pratap Airport", "Udaipur", "IN", 24.6177, 73.8961, "Asia/Kolkata"),
    AirportRef("DXB", "Dubai International Airport", "Dubai", "AE", 25.2532, 55.3657, "Asia/Dubai"),
    AirportRef(
        "SIN", "Singapore Changi Airport", "Singapore", "SG", 1.3644, 103.9915, "Asia/Singapore"
    ),
    AirportRef("BKK", "Suvarnabhumi Airport", "Bangkok", "TH", 13.6900, 100.7501, "Asia/Bangkok"),
    AirportRef("LHR", "London Heathrow Airport", "London", "GB", 51.4700, -0.4543, "Europe/London"),
    AirportRef(
        "CMB",
        "Bandaranaike International Airport",
        "Colombo",
        "LK",
        7.1808,
        79.8841,
        "Asia/Colombo",
    ),
    AirportRef(
        "KTM",
        "Tribhuvan International Airport",
        "Kathmandu",
        "NP",
        27.6966,
        85.3591,
        "Asia/Kathmandu",
    ),
    AirportRef("DOH", "Hamad International Airport", "Doha", "QA", 25.2731, 51.6081, "Asia/Qatar"),
)

CITIES: tuple[CityRef, ...] = (
    CityRef("Delhi", "IN", 28.6139, 77.2090, "INR", "metro", 1, ("DEL",)),
    CityRef("Mumbai", "IN", 19.0760, 72.8777, "INR", "metro", 1, ("BOM",)),
    CityRef("Bengaluru", "IN", 12.9716, 77.5946, "INR", "metro", 1, ("BLR",)),
    CityRef("Chennai", "IN", 13.0827, 80.2707, "INR", "metro", 1, ("MAA",)),
    CityRef("Kolkata", "IN", 22.5726, 88.3639, "INR", "metro", 1, ("CCU",)),
    CityRef("Hyderabad", "IN", 17.3850, 78.4867, "INR", "metro", 1, ("HYD",)),
    CityRef("Goa", "IN", 15.4909, 73.8278, "INR", "beach", 2, ("GOI",)),
    CityRef("Kochi", "IN", 9.9312, 76.2673, "INR", "beach", 2, ("COK",)),
    CityRef("Jaipur", "IN", 26.9124, 75.7873, "INR", "heritage", 2, ("JAI",)),
    CityRef("Ahmedabad", "IN", 23.0225, 72.5714, "INR", "metro", 2, ("AMD",)),
    CityRef("Pune", "IN", 18.5204, 73.8567, "INR", "metro", 2, ("PNQ",)),
    CityRef("Lucknow", "IN", 26.8467, 80.9462, "INR", "heritage", 3, ("LKO",)),
    CityRef("Amritsar", "IN", 31.6340, 74.8723, "INR", "spiritual", 3, ("ATQ",)),
    CityRef("Varanasi", "IN", 25.3176, 82.9739, "INR", "spiritual", 3, ("VNS",)),
    CityRef("Srinagar", "IN", 34.0837, 74.7973, "INR", "hill", 3, ("SXR",)),
    CityRef("Port Blair", "IN", 11.6234, 92.7265, "INR", "beach", 3, ("IXZ",)),
    CityRef("Thiruvananthapuram", "IN", 8.5241, 76.9366, "INR", "beach", 3, ("TRV",)),
    CityRef("Udaipur", "IN", 24.5854, 73.7125, "INR", "heritage", 3, ("UDR",)),
    CityRef("Dubai", "AE", 25.2048, 55.2708, "AED", "international", 1, ("DXB",)),
    CityRef("Singapore", "SG", 1.3521, 103.8198, "SGD", "international", 1, ("SIN",)),
    CityRef("Bangkok", "TH", 13.7563, 100.5018, "THB", "international", 1, ("BKK",)),
    CityRef("London", "GB", 51.5074, -0.1278, "GBP", "international", 1, ("LHR",)),
    CityRef("Colombo", "LK", 6.9271, 79.8612, "LKR", "international", 2, ("CMB",)),
    CityRef("Kathmandu", "NP", 27.7172, 85.3240, "NPR", "international", 2, ("KTM",)),
    CityRef("Doha", "QA", 25.2854, 51.5310, "QAR", "international", 2, ("DOH",)),
)

# Approximate units of local currency per 1 INR, used only to price synthetic rates in local
# currency. These are not quotes; real conversion rates belong in config/rules.yaml.
SYNTHETIC_INR_TO_LOCAL: dict[str, float] = {
    "INR": 1.0,
    "AED": 0.044,
    "SGD": 0.0155,
    "THB": 0.41,
    "GBP": 0.0094,
    "LKR": 3.5,
    "NPR": 1.6,
    "QAR": 0.044,
}

HUBS = ("DEL", "BOM", "BLR", "MAA", "CCU", "HYD")
INTERNATIONAL_GATEWAYS = ("DEL", "BOM", "BLR", "MAA", "COK", "HYD")

# Fictional carriers. Codes are arbitrary two-letter tokens for the demo.
AIRLINES: tuple[tuple[str, str], ...] = (
    ("Saffron Skies", "SF"),
    ("Monsoon Air", "MZ"),
    ("Coastline Airways", "CW"),
    ("Peak Air", "PJ"),
)
