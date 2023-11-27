# pyportal-accessibility-map
Display a map of wheelchair accessible venues on the PyPortal

This repository contains the code and 3D models required to build an interactive display for finding wheelchair-accessible places. Read the full project description and build tutorial on [Hackster.io](https://www.hackster.io/rhammell/interactive-display-for-finding-wheelchair-accessible-places-6020f1)

## How It Works
This interactive display enables users to discover nearby places that include wheelchair-accessible options. It is a prototype of a full-scale display that would be installed in popular public areas to aid people with mobility impairments in finding places that can accommodate their needs.

When powered on, the display connects to the internet and collects map images and place data it uses to build an interactive visualization.

The visualization shows a map centered on a user-defined location, with icons highlighting the locations of places - restaurants, theaters, shops, etc. - that have wheelchair-accessible options.

Users can touch any icon on the map, which will update the display to show the selected place's details. These details include the place name, address, distance from the center of the map, and a list of available wheelchair options (parking, seating, entrances, restrooms).

Map images are provided by Geoapify, and place data is obtained from the Google Places API.

## Demo Video
[![Video](https://img.youtube.com/vi/4iSLRZ3ODrE/0.jpg)](https://www.youtube.com/watch?v=4iSLRZ3ODrE)
