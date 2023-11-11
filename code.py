import math
import json
import time
import board
import busio
import displayio
import terminalio
import neopixel
import digitalio
import adafruit_touchscreen
import adafruit_imageload
from adafruit_bitmap_font import bitmap_font
from adafruit_display_shapes.rect import Rect
from adafruit_display_text import label, wrap_text_to_pixels
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_esp32spi import adafruit_esp32spi_wifimanager


# Import secrets file
try:
    from secrets import secrets
except ImportError:
    print("Missing secrets.py file!")
    raise


def map_range(value, in_min, in_max, out_min, out_max):
    ''' Map input value to output range '''

    return out_min + (((value - in_min) / (in_max - in_min)) * (out_max - out_min))


def calc_pixel_coordinate(lat, lon, image_width, image_height, lat_min, lat_max, lon_min, lon_max):
    ''' Return x/y pixel coordinate for input lat/lon values, for
        given image size and bounds
    '''

    # Calculate x-coordinate
    x = map_range(lon, lon_min, lon_max, 0, image_width)

    # Calculate y-coordinate using the Mercator projection
    lat_rad = math.radians(lat)
    lat_max_rad = math.radians(lat_max)
    lat_min_rad = math.radians(lat_min)
    merc_lat = math.log(math.tan(math.pi/4 + lat_rad/2))
    merc_max = math.log(math.tan(math.pi/4 + lat_max_rad/2))
    merc_min = math.log(math.tan(math.pi/4 + lat_min_rad/2))
    y = map_range(merc_lat, merc_max, merc_min, 0, image_height)

    return int(x), int(y)


def geo_bounds(lat, lon, radius, ratio=1):
    ''' Return min/max box bounds for circle centered on input
        lat/lon coordinate with input radius (Km)

        Box bounds will be adjusted to result in
        a box whose short axis fits the circle
        and long axis is extended to result in box
        with an width:height ratio matching the
        input ratio value
    '''

    # Set earth radius
    EARTH_RADIUS = 6378.1

    # Convert to radians
    rad_lat = math.radians(lat)
    rad_lon = math.radians(lon)

    # Calculate radius in radians
    rad_radius = radius / EARTH_RADIUS

    # Calculate radius deltas
    delta_lat = rad_radius
    delta_lon = math.asin(math.sin(rad_radius) / math.cos(rad_lat))
    if ratio < 1:
        delta_lat /= ratio
    else:
        delta_lon *= ratio

    # Calculate latitude bounds
    min_rad_lat = rad_lat - delta_lat
    max_rad_lat = rad_lat + delta_lat

    # Calculate longitude bounds
    min_rad_lon = rad_lon - delta_lon
    max_rad_lon = rad_lon + delta_lon

    # Convert from radians to degrees
    max_lat = math.degrees(max_rad_lat)
    min_lat = math.degrees(min_rad_lat)
    max_lon = math.degrees(max_rad_lon)
    min_lon = math.degrees(min_rad_lon)

    return max_lat, min_lat, max_lon, min_lon


def haversine_distance(lat1, lon1, lat2, lon2):
    # Radius of the Earth in meters
    earth_radius = 6371000  # Approximate value for the Earth's radius in meters

    # Convert latitude and longitude from degrees to radians
    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Calculate the distance
    distance = earth_radius * c

    return distance


def url_encode(string):
    ''' Return URL encoding of input string '''

    encoded_string = ''
    for char in string:
        if char.isalpha() or char.isdigit() or char in ('-', '_', '.', '~'):
            encoded_string += char
        else:
            encoded_string += '%' + '{:02X}'.format(ord(char))

    return encoded_string


def build_url(url, params={}):
    ''' Return URL with formatted parameters added '''

    params_str = "&".join(["%s=%s" % (key, value) for key, value in params.items()])
    return url + "?" + params_str


def download_file(url, fname, chunk_size=4096, headers=None):
    ''' Download file from URL and store locally '''

    # Request url
    response = wifi.get(url, stream=True)

    # Determine content length from response
    headers = {}
    for title, content in response.headers.items():
        headers[title.lower()] = content
    content_length = int(headers["content-length"])

    # Save streaming data to output file
    remaining = content_length
    stamp = time.monotonic()
    with open(fname, "wb") as file:
        for i in response.iter_content(min(remaining, chunk_size)):
            remaining -= len(i)
            file.write(i)
            if not remaining:
                break
    response.close()

def icon_touched(x, y, size, touch):
    ''' Return true if touch event occurs within
        the map icon bounds of the input place '''

    return x - size/2 <= touch[0] < x + size/2 and \
           y - size/2 <= touch[1] < y + size/2


def update_place_view(place):
    ''' Update place view elements with
        information from input place dictionary '''

    # Remove previous place details
    while len(place_info_group) > 0:
        place_info_group.pop(0)

    # Add place name
    name = place["displayName"]["text"]
    name_offset = 15
    name_lines = wrap_text_to_pixels(name, 210, font)
    for i, name_line in enumerate(name_lines):
        place_info_group.append(label.Label(
            font = font,
            color=0x4b4b4b,
            anchor_point=(0.5,0.0),
            anchored_position=(120, name_offset + i*20),
            text=name_line
        ))

    # Calculate distance to place from center
    place_lat = place["location"]["latitude"]
    place_lon = place["location"]["longitude"]
    distance = int(haversine_distance(center_lat, center_lon, place_lat, place_lon))

    # Add place address
    address_offset = name_offset + len(name_lines)*20 + 3
    place_info_group.append(label.Label(
        font = terminalio.FONT,
        color=0x545454,
        anchor_point=(0.5,0.0),
        anchored_position=(120, address_offset),
        text=place["formattedAddress"].split(',')[0] + ' | ' + str(distance) + ' m'
    ))

    # Display accessibility information
    access_offset = address_offset + 20
    access_height = 58
    for i, option in enumerate(place["accessibilityOptions"]):
        if place["accessibilityOptions"][option] == True:
            option_name = accessibility_options_formatted[option]["name"]
            option_icon = accessibility_options_formatted[option]["icon"]
            place_info_group.append(Rect(
                15,
                access_offset + i*access_height,
                display.width-30,
                access_height-5,
                fill=0xcdcdcd,
                outline=0x4b4b4b
            ))
            place_info_group.append(label.Label(
                font = font,
                color=0x545454,
                anchor_point=(0.5,0.5),
                anchored_position=(120, access_offset + i*access_height + (access_height-5)/2),
                text=option_name
            ))
            place_info_group.append(displayio.TileGrid(
                option_icon,
                pixel_shader=option_icon.pixel_shader,
                x = 25,
                y = int(access_offset + i*access_height + (access_height-5)/2-16)
            ))
            place_info_group.append(displayio.TileGrid(
                check_icon,
                pixel_shader=check_icon.pixel_shader,
                x = 240 - 15 - 32 -10,
                y = int(access_offset + i*access_height + (access_height-5)/2-16)
            ))


# Create display
display = board.DISPLAY
display.rotation = 270
display.brightness = 0.5

# Load fonts
font_file = "fonts/OpenSans-Bold-20.bdf"
font = bitmap_font.load_font(font_file)

# Touchscreen configuration
ts = adafruit_touchscreen.Touchscreen(
    board.TOUCH_YD,
    board.TOUCH_YU,
    board.TOUCH_XR,
    board.TOUCH_XL,
    calibration=((8000, 54000), (8300, 59000)),
    size=(display.width, display.height)
)

# Touch tracking
touch_active = False;
release_threshold = 2;
release_count = 0;

# Didplay options
current_view = 0

# Create main display groups
main_group = displayio.Group()
display.root_group = main_group

# Create map display group
map_group = displayio.Group()
map_group.hidden = True
main_group.append(map_group)

# Create details display group
place_group = displayio.Group()
place_info_group = displayio.Group()
place_background = Rect(0, 0, display.width, display.height, fill=0xFFFFFF)
place_group.append(place_background)
place_group.append(place_info_group)
place_group.hidden = True
main_group.append(place_group)

# Load details images
parking_icon = displayio.OnDiskBitmap('img/parking_icon.bmp')
parking_icon.pixel_shader.make_transparent(0)
entrance_icon = displayio.OnDiskBitmap('img/entrance_icon.bmp')
entrance_icon.pixel_shader.make_transparent(0)
seating_icon = displayio.OnDiskBitmap('img/seating_icon.bmp')
seating_icon.pixel_shader.make_transparent(0)
restroom_icon = displayio.OnDiskBitmap('img/restroom_icon.bmp')
restroom_icon.pixel_shader.make_transparent(0)
check_icon = displayio.OnDiskBitmap('img/check_icon.bmp')
check_icon.pixel_shader.make_transparent(0)

# Formatted
accessibility_options_formatted = {
    "wheelchairAccessibleParking": {"name": "Parking", "icon": parking_icon},
    "wheelchairAccessibleEntrance": {"name": "Entrance", "icon": entrance_icon},
    "wheelchairAccessibleRestroom": {"name": "Restroom", "icon": restroom_icon},
    "wheelchairAccessibleSeating": {"name": "Seating", "icon": seating_icon}
}

# Create splash display group
splash_group = displayio.Group()
main_group.append(splash_group)

# Display splash image
splash_image = displayio.OnDiskBitmap("img/splash.bmp")
splash_sprite = displayio.TileGrid(splash_image, pixel_shader=splash_image.pixel_shader)
splash_label = label.Label(
    font = terminalio.FONT,
    color=0xFFFFFF,
    anchor_point=(0.5,0.0),
    anchored_position=(120,208),
)
splash_group.append(splash_sprite)
splash_group.append(splash_label)

# Configure WIFI manager
esp32_cs = digitalio.DigitalInOut(board.ESP_CS)
esp32_ready = digitalio.DigitalInOut(board.ESP_BUSY)
esp32_reset = digitalio.DigitalInOut(board.ESP_RESET)
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
status_light = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.2)
wifi = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp, secrets, status_light)

# Connect WiFi
splash_label.text = "Connecting to WiFi..."
print("Connecting to WiFi...")
wifi.connect()

# Define map center
center_lat = 38.0305
center_lon = -78.4807

# Map radius (km)
radius_km = 0.1

# Calculate map bounds
lat_max, lat_min, lon_max, lon_min = geo_bounds(center_lat, center_lon, radius_km, ratio=display.width/display.height)

# Geoapify map parameters
map_params = {
    "style": "toner",
    "width": display.width * 2,
    "height": display.height * 2,
    "apiKey": secrets["geoapify_api_key"],
    "format": "png",
    "area": "rect:%f,%f,%f,%f" % (lon_max, lat_max, lon_min, lat_min),
    "geometry": "circle:" + str(lon_min) + "," + str(lat_min) + ",30" + "|" + \
                "circle:" + str(lon_max) + "," + str(lat_min) + ",30" + "|" + \
                "circle:" + str(lon_min) + "," + str(lat_max) + ",30" + "|" + \
                "circle:" + str(lon_max) + "," + str(lat_max) + ",30"
}

# Build Geoapify map URL
map_url = build_url("https://maps.geoapify.com/v1/staticmap", map_params)
print(map_url)

# Adafruit IO image convert parameters
convert_params = {
    "x-aio-key": secrets["adafruit_io_key"],
    "width": display.width,
    "height": display.height,
    "output": "BMP16",
    "url": url_encode(map_url)
}

# Build Adafruit IO image convert URL
convert_url = build_url(
    f"https://io.adafruit.com/api/v2/{secrets["adafruit_io_username"]}/integrations/image-formatter",
    convert_params
)

# Download converted map image
map_fname = "img/map.bmp"
splash_label.text = "Downloading map..."
print("Downloading map image...")
download_file(convert_url, map_fname)

# Display map image
map_image = displayio.OnDiskBitmap(map_fname)
map_sprite = displayio.TileGrid(map_image, pixel_shader=map_image.pixel_shader)
map_group.append(map_sprite)

# Load map icon
icon_image = displayio.OnDiskBitmap('img/map_icon.bmp')
icon_image.pixel_shader.make_transparent(0)
icon_size = 20

# Google Places API search parameters
places_url = "https://places.googleapis.com/v1/places:searchNearby"
fields = [
    "places.displayName",
    "places.accessibilityOptions",
    "places.formattedAddress",
    "places.id","places.location",
    "places.primaryTypeDisplayName"
]
headers = {
    "X-Goog-Api-Key": secrets["google_api_key"],
    "X-Goog-FieldMask": ",".join(fields)
}
body = {
  "maxResultCount": 15,
  "locationRestriction": {
    "circle": {
      "center": {
        "latitude": center_lat,
        "longitude": center_lon},
      "radius": radius_km * 1000
    }
  }
}

# Make Google Places request
splash_label.text = "Requesting map data..."
print("Requesting map data...")
response = wifi.post(places_url, headers=headers, data=json.dumps(body))
data = response.json()
splash_label.text = ""

# Loop through resulting places
if "places" in data:
    for place in data["places"]:

        # Get location data
        lon = place["location"]["longitude"]
        lat = place["location"]["latitude"]

        # Convert location to pixel x/y coordinate
        x, y = calc_pixel_coordinate(lat, lon, display.width, display.height, lat_min, lat_max, lon_min, lon_max)

        # Display map icon
        icon = displayio.TileGrid(
            icon_image,
            pixel_shader=icon_image.pixel_shader,
            x = x - int(icon_size/2),
            y = y - int(icon_size/2)
        )
        map_group.append(icon)

        # Store place x/y coordinate
        place["x"] = x
        place["y"] = y

# Hide splash and show map
splash_group.hidden = True
map_group.hidden = False

# Main processing loop
while True:
    time.sleep(0.1)

    # Process touch event
    touch = ts.touch_point
    if touch:
        print(touch)
        # Handle touch on map views
        if current_view == 0:

            # Process map icon touch
            for place in data["places"]:
                is_touched = icon_touched(place["x"], place["y"], icon_size, touch)
                if is_touched and touch_active == False:
                    update_place_view(place)
                    release_count = 0;
                    touch_active = True
                    break

        # Handle touch on place view
        else:
            if touch_active == False:
                release_count = 0
                touch_active = True

    # Process no touch
    else:
        # Handle release after touch event
        if touch_active == True:
            if release_count >= release_threshold:
                touch_active = False

                # Update display view
                if current_view == 0:
                    map_group.hidden = True
                    place_group.hidden = False
                    current_view = 1
                else:
                    map_group.hidden = False
                    place_group.hidden = True
                    current_view = 0
            else:
                release_count += 1
