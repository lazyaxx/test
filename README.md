Mobile MCP Server Tools
The Mobile MCP server provides a comprehensive set of tools for mobile automation, testing, and interaction across iOS and Android platforms. This Model Context Protocol server enables seamless control of simulators, emulators, and physical devices through a unified interface.
Device Management Tools
mobile_use_default_device
	•	Purpose: Automatically selects the default device when only one is available
	•	Parameters: None
	•	Description: Provides a quick way to connect to a device without manual selection. If multiple devices are found, it will prompt you to use the device listing tool instead.
mobile_list_available_devices
	•	Purpose: Lists all connected devices and simulators
	•	Parameters: None
	•	Description: Displays iOS simulators, physical iOS devices, Android mobile devices, and Android TV devices that are currently available for automation.
mobile_use_device
	•	Purpose: Manually select a specific device to control
	•	Parameters:
	•	`device`: Name of the device to select
	•	`deviceType`: Type of device (“simulator”, “ios”, or “android”)
	•	Description: Allows precise device selection for automation tasks.
Application Management Tools
mobile_list_apps
	•	Purpose: Lists all installed applications on the selected device
	•	Parameters: None
	•	Description: Returns app names and package identifiers for all installed applications.
mobile_launch_app
	•	Purpose: Launches a specific application
	•	Parameters:
	•	`packageName`: The package name of the app to launch
	•	Description: Opens the specified app on the device. Package names can be found using the list_apps tool.
mobile_terminate_app
	•	Purpose: Stops and terminates a running application
	•	Parameters:
	•	`packageName`: The package name of the app to terminate
	•	Description: Forcefully closes the specified application.
Screen Interaction Tools
mobile_take_screenshot
	•	Purpose: Captures a screenshot of the current screen
	•	Parameters: None
	•	Description: Returns a base64-encoded image of the current screen state. Supports automatic image optimization with ImageMagick when available.
mobile_save_screenshot
	•	Purpose: Saves a screenshot to a specified file path
	•	Parameters:
	•	`saveTo`: File path where the screenshot should be saved
	•	Description: Captures and saves a screenshot to the local filesystem.
mobile_get_screen_size
	•	Purpose: Retrieves the screen dimensions
	•	Parameters: None
	•	Description: Returns the width and height of the device screen in pixels.
mobile_click_on_screen_at_coordinates
	•	Purpose: Performs a tap at specific screen coordinates
	•	Parameters:
	•	`x`: X coordinate in pixels
	•	`y`: Y coordinate in pixels
	•	Description: Simulates a finger tap at the specified location on the screen.
mobile_list_elements_on_screen
	•	Purpose: Lists all interactive elements visible on the screen
	•	Parameters: None
	•	Description: Returns detailed information about UI elements including their type, text, labels, coordinates, and accessibility properties. This provides structured data for more reliable automation compared to coordinate-based approaches.
Navigation and Input Tools
swipe_on_screen
	•	Purpose: Performs swipe gestures on the screen
	•	Parameters:
	•	`direction`: Direction to swipe (“up”, “down”, “left”, “right”)
	•	`x` (optional): Starting X coordinate
	•	`y` (optional): Starting Y coordinate
	•	`distance` (optional): Distance to swipe in pixels
	•	Description: Simulates finger swipe gestures, useful for scrolling, navigation, and gesture-based interactions.
mobile_type_keys
	•	Purpose: Types text into the currently focused input field
	•	Parameters:
	•	`text`: The text to type
	•	`submit`: Whether to submit the text (press Enter)
	•	Description: Simulates keyboard input for filling forms and text fields.
mobile_press_button
	•	Purpose: Presses hardware or system buttons
	•	Parameters:
	•	`button`: Button name (BACK, HOME, VOLUME_UP, VOLUME_DOWN, ENTER, DPAD_CENTER, DPAD_UP, DPAD_DOWN, DPAD_LEFT, DPAD_RIGHT)
	•	Description: Simulates physical button presses. Some buttons are platform-specific (e.g., BACK for Android only, DPAD buttons for Android TV).
Advanced Features
mobile_open_url
	•	Purpose: Opens a URL in the default browser
	•	Parameters:
	•	`url`: The URL to open
	•	Description: Launches the default browser and navigates to the specified URL.
mobile_set_orientation
	•	Purpose: Changes the device screen orientation
	•	Parameters:
	•	`orientation`: Desired orientation (“portrait” or “landscape”)
	•	Description: Rotates the device screen to the specified orientation.
mobile_get_orientation
	•	Purpose: Gets the current screen orientation
	•	Parameters: None
	•	Description: Returns the current device orientation state.
Key Features
The server is designed with several important characteristics:
	•	Platform Agnostic: Works with both iOS and Android devices without requiring platform-specific knowledge
	•	Accessibility-First: Prioritizes structured accessibility data over screenshot-based approaches for more reliable automation
	•	Visual Fallback: Uses screenshot analysis when accessibility data is unavailable
	•	Multiple Device Support: Handles simulators, emulators, and physical devices seamlessly
	•	LLM-Friendly: Designed specifically for integration with AI agents and language models
This comprehensive tool set enables complex mobile automation workflows, from simple app testing to sophisticated multi-step user journey automation, all through a unified programmatic interface.