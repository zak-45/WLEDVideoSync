"""
a: zak-45
d: 06/11/2025
v: 1.2.0

Overview:
This file defines the `ActionExecutor` class, which serves as the command processing engine for the background
casting threads (`CASTDesktop` and `CASTMedia`). Its primary role is to take action requests from a list,
parse them, and execute the corresponding logic in a structured and safe manner.

The design of this class is critical for performance. It is instantiated **once** per casting thread at the beginning
of the thread's lifecycle and is then reused for every subsequent action. This avoids the significant overhead of
creating new objects within the real-time video processing loop.

Key Architectural Components:

1.  ActionExecutor Class:
    -   **Purpose**: To encapsulate the logic for all possible actions that can be performed on a running cast,
        such as stopping the stream, taking a snapshot, or changing the target IP address.

    -   **Initialization (`__init__`)**:
        -   The constructor is designed to be called once, capturing the **static context** of the casting thread.
          This includes non-changing data like the thread's name, the logger instance, IP addresses, and other
          configuration parameters.
        -   This makes the `ActionExecutor` a stateful object that is tightly coupled with the specific thread it serves.

    -   **Execution (`process_actions`)**:
        -   This is the main public method, called from within the casting loop whenever there are pending actions.
        -   It accepts the **dynamic context**—information that changes on every frame, namely the `frame` and
          `frame_count`.
        -   It iterates through the shared `cast_name_todo` list, identifies actions meant for its specific thread,
          and calls the appropriate handler.
        -   It returns a list of the actions it has processed, allowing the calling thread to safely remove them
          from the shared queue.

    -   **Action Dispatch (`_ACTION_HANDLERS_MAP`)**:
        -   The class uses a static dictionary to map action strings (e.g., 'shot', 'stop') to their corresponding
          handler methods (e.g., `_handle_snapshot_action`).
        -   This dispatch table pattern is clean, efficient, and makes the system highly extensible. To add a new
          action, a developer only needs to add a new handler method and an entry in this map.

    -   **State Management**:
        -   The handler methods directly modify the state of the parent casting object (`self.class_obj`) or the
          executor's own internal flags (`self.t_todo_stop`, `self.t_preview`). This keeps the state changes
          encapsulated and predictable.

Design Philosophy:
-   **Performance**: The "instantiate-once, reuse-many" pattern is crucial for avoiding performance bottlenecks in
    the real-time video loop.
-   **Decoupling**: The executor separates the "what" (the action logic) from the "when" (the loop management in the
    casting thread). The casting thread manages the queue, while the executor handles the implementation details of
    each action.
-   **Extensibility**: The use of a dispatch dictionary makes it straightforward to add new actions in the future
    without altering the core processing loop.
"""
import traceback

from threading import current_thread
from str2bool import str2bool

from src.utl.cv2utils import CV2Utils, ImageUtils
from src.utl.utils import CASTUtils as Utils

class ActionExecutor:
    """
    Manages and executes actions requested for a specific casting thread (Media or Desktop).
    """

    # Define the handlers map at the class level to be accessible by the static method
    # This makes the list of actions static and accessible without an instance.
    _ACTION_HANDLERS_MAP = {
        'stop': '_handle_stop_action',
        'shot': '_handle_snapshot_action',
        'info': '_handle_info_action',
        'reset': '_handle_reset_action',
        'host': '_handle_host_action',
        'multicast': '_handle_multicast_action',
        'close-preview': '_handle_close_preview',
        'open-preview': '_handle_open_preview',
        'stop-text': '_handle_stop_text_action'
    }

    def __init__(self,
                 class_obj,  # Media or Desktop class instance containing state like cast_name_todo
                 port,  # server port
                 t_name,  # Thread name
                 t_viinput,  # Video input source identifier
                 t_scale_width,  # Target width for scaling/processing
                 t_scale_height,  # Target height for scaling/processing
                 t_multicast,  # Multicast flag
                 ip_addresses,  # List of target IP addresses (mutable, first element might change)
                 ddp_host,  # DDP device instance (can be None)
                 t_cast_x,  # Cast X coordinate (for multicast grid?)
                 t_cast_y,  # Cast Y coordinate (for multicast grid?)
                 start_time,  # Initial start time of the process
                 initial_preview_state,  # Initial state of the preview window flag
                 fps,  # Target FPS/interval
                 media_length,  # Total length of the media (if applicable)
                 swapper,  # Swapper instance for multicast effects
                 shared_buffer,  # Queue for inter-thread communication
                 logger,  # Logger instance
                 t_protocol):  # Protocol used for streaming (e.g., 'ddp', 'artnet')
        """
        Initializes the ActionExecutor with the context and state of the casting thread.
        """
        self.class_obj = class_obj
        self.port = port
        self.t_name = t_name
        self.t_viinput = t_viinput
        self.t_scale_width = t_scale_width
        self.t_scale_height = t_scale_height
        self.t_multicast = t_multicast
        self.ip_addresses = ip_addresses  # Note: This is a mutable list reference
        self.ddp_host = ddp_host  # Note: This is an object reference
        self.t_cast_x = t_cast_x
        self.t_cast_y = t_cast_y
        self.start_time = start_time
        self.fps = fps
        self.media_length = media_length
        self.swapper = swapper
        self.shared_buffer = shared_buffer
        self.logger = logger
        self.t_protocol = t_protocol

        # for snapshot if requested
        self.frame_buffer = None
        self.cast_frame_buffer = None

        # Internal state flags managed by actions
        self.t_preview = initial_preview_state
        self.t_todo_stop = False

        # Action handlers dictionary
        self._action_handlers = {key: getattr(self, method_name) for key, method_name in self._ACTION_HANDLERS_MAP.items()}

    # --- Private Handler Methods ---

    def _handle_snapshot_action(self, frame, params, frame_count):
        """Handles the 'shot' action: captures and processes a snapshot frame."""
        # params are currently unused for 'shot', but kept for consistency
        add_frame = CV2Utils.pixelart_image(frame, self.t_scale_width, self.t_scale_height)
        add_frame = CV2Utils.resize_image(add_frame, self.t_scale_width, self.t_scale_height)
        if self.t_multicast:
            # Assuming the original frame is needed for multicast snapshot sizing
            add_frame = CV2Utils.resize_image(frame, self.t_scale_width * self.t_cast_x,
                                              self.t_scale_height * self.t_cast_y)

        self.frame_buffer=add_frame
        self.logger.debug(f'{self.t_name}: Snapshot taken.')

    def _handle_info_action(self, frame, params, frame_count):
        """Handles the 'info' action: sends thread status information."""
        # Determine if image data should be included based on params
        include_image = str2bool(params) if params else False  # Default to not including image if params missing

        if str(self.t_viinput) != "queue" and include_image:
            # Only encode if needed and possible
            try:
                img_b64 = ImageUtils.image_array_to_base64(frame)
            except Exception as img_err:
                self.logger.error(f"{self.t_name}: Error encoding image for info: {img_err}")
                img_b64 = "Error"
        else:
            img_b64 = "None"  # Explicitly "None" if queue input or not requested

        t_info = {self.t_name: {
            "type": "info",
            "data": {
                "start": self.start_time,
                "cast_type": self.class_obj.__class__.__name__,  # Get class name correctly
                "tid": current_thread().native_id,
                "viinput": str(self.t_viinput),
                "preview": self.t_preview,
                "protocol": self.t_protocol,
                "multicast": self.t_multicast,
                "devices": list(self.ip_addresses),  # Send a copy of the current list
                "image": {
                    "W": self.t_scale_width,
                    "H": self.t_scale_height
                },
                "fps": self.fps,
                "frames": frame_count,  # Use passed frame_count
                "length": self.media_length,
                "img": img_b64
            }
        }}
        if self.shared_buffer is not None:
            try:
                self.shared_buffer.put(t_info)
                self.logger.debug(f'{self.t_name}: Info put in shared buffer.')
            except Exception as q_err:
                self.logger.error(f"{self.t_name}: Failed to put info in shared buffer: {q_err}")
        else:
            self.logger.error(f'{self.t_name}: Shared buffer missing for info action.')

    def _handle_multicast_action(self, params):
        """Handles the 'multicast' action: controls multicast effects via swapper."""
        if not self.t_multicast:
            self.logger.warning(f'{self.t_name}: Multicast action ignored (not in multicast mode).')
            return

        if not params:
            self.logger.error(f'{self.t_name}: Missing parameters for multicast action.')
            return

        try:
            if params.lower() == 'stop':
                action_arg = 'stop'
                delay_arg = 0
            else:
                parts = params.split(',')
                if len(parts) != 2:
                    raise ValueError("Expected format: action,delay")
                action_arg = parts[0].strip().lower()
                delay_arg = int(parts[1].strip())
        except ValueError as e:
            self.logger.error(f'{self.t_name}: Invalid multicast params "{params}". Error: {e}')
            return
        except Exception as e:
            self.logger.error(f'{self.t_name}: Error parsing multicast params "{params}". Error: {e}')
            return

        # Check before starting a new effect if one is running (except for 'stop')
        if self.swapper.running and action_arg != 'stop':
            self.logger.warning(
                f'{self.t_name}: Cannot start multicast effect "{action_arg}", another effect is already running.')
            return

        # Execute swapper actions
        action_map = {
            'circular': lambda delay: self.swapper.start_circular_swap(delay),
            'reverse': lambda delay: self.swapper.start_reverse_swap(delay),
            'random': lambda delay: self.swapper.start_random_order(delay),
            'pause': lambda delay: self.swapper.start_random_replace(delay),  # Assuming 'pause' maps to random_replace
            'stop': lambda delay: self.swapper.stop()  # Delay arg ignored for stop
        }

        if handler := action_map.get(action_arg):
            self.logger.info(f'{self.t_name}: Executing multicast action "{action_arg}" with delay {delay_arg}.')
            try:
                handler(delay_arg)
            except Exception as swap_err:
                self.logger.error(f'{self.t_name}: Error executing swapper action "{action_arg}": {swap_err}')
        else:
            self.logger.error(f'{self.t_name}: Unknown multicast action command "{action_arg}" in params "{params}".')

    def _handle_host_action(self, params):
        """Handles the 'host' action: changes the primary target IP address."""
        if not params:
            self.logger.error(f'{self.t_name}: Missing IP address for host action.')
            return

        new_ip = params.strip()
        # Optional: Add IP validation here if needed
        if not Utils.validate_ip_address(new_ip):
             self.logger.error(f'{self.t_name}: Invalid IP address provided for host action: {new_ip}')
             return

        self.logger.info(f'{self.t_name}: Changing host IP to {new_ip}.')
        self.ip_addresses[0] = new_ip  # Update the shared list

        # Update DDP host if it exists
        if self.ddp_host:
            try:
                # Assuming DDPDevice has a way to update destination or needs re-initialization
                # This might need adjustment based on DDPDevice's actual API
                self.ddp_host._destination = new_ip  # Example: Directly setting attribute
                self.logger.debug(f'{self.t_name}: Updated existing DDP host destination.')
            except AttributeError:
                self.logger.warning(f'{self.t_name}: Could not update DDP host destination attribute.')
            except Exception as ddp_err:
                self.logger.error(f'{self.t_name}: Error updating DDP host: {ddp_err}')
        # else:
        # Decide if a new DDPDevice should be created if one wasn't present
        # self.ddp_host = DDPDevice(new_ip) # Creates a new one, might not be desired
        # self.logger.debug(f'{self.t_name}: No existing DDP host to update.')
        # pass # Or simply do nothing if no ddp_host was initially provided

    def _handle_reset_action(self, params):
        """Handles the 'reset' action: resets frame/packet counters on the class_obj."""
        # params are currently unused for 'reset'
        try:
            # Assuming class_obj has these attributes
            self.class_obj.total_frames = 0
            self.class_obj.total_packets = 0
            # self.class_obj.reset_total = False # Is this flag still needed? Resetting implies it's done.
            self.logger.info(f'{self.t_name}: Frame and packet counters reset.')
        except AttributeError as e:
            self.logger.error(f'{self.t_name}: Failed to reset counters on class_obj: {e}')

    def _handle_stop_text_action(self, params):
        """Handles the 'stop-text' action: allow or not text overlay on the class_obj."""
        # params are currently unused for 'stop-text'
        try:
            # Assuming class_obj has these attributes
            self.class_obj.allow_text_animator = False
            self.logger.info(f'{self.t_name}: put allow text animator to False.')
        except AttributeError as e:
            self.logger.error(f'{self.t_name}: Failed to put allow text animator to False on class_obj: {e}')

    def _handle_close_preview(self, params):
        """Handles the 'close-preview' action."""
        if self.t_preview:
            self.logger.info(f'{self.t_name}: Closing preview window.')
            CV2Utils.cv2_win_close(self.port, self.class_obj.__class__.__name__, self.t_name, self.t_viinput)
            self.t_preview = False

    def _handle_open_preview(self, params):
        """Handles the 'open-preview' action."""
        if not self.t_preview:
            self.logger.info(f'{self.t_name}: Opening preview window.')
            self.t_preview = True

    def _handle_stop_action(self, params):
        """Handles the 'stop' action: sets the stop flag."""
        # params are currently unused for 'stop'
        self.logger.info(f'{self.t_name}: Stop action received.')
        self.t_todo_stop = True

    # --- Public Execution Method ---

    def process_actions(self, frame, frame_count):
        """
        Processes actions pending in the class_obj.cast_name_todo list for the current thread.

        Args:
            frame: The current video/image frame to be used by actions like 'shot' or 'info'.
            frame_count: The current frame count, used by actions like 'info'.

        Returns:
            tuple: A tuple containing the updated (t_todo_stop, t_preview, frame_buffer, cast_frame_buffer, cast_name_todo).
        """
        import re

        self.cast_frame_buffer = None
        self.frame_buffer = None

        # Use a robust regex to split action items, allowing for extra delimiters in params
        def parse_action_item(item):
            # Expected format: name||action||params||added_time
            # Allow params to contain '||' by splitting only the first three
            parts = item.split('||', 3)
            if len(parts) != 4:
                return None
            name, action, params, added_time = [p.strip() for p in parts]
            return name, action, params, added_time

        # Use a new list to collect valid actions
        new_todo = []
        for item in list(self.class_obj.cast_name_todo):
            parsed = parse_action_item(item)
            if not parsed:
                self.logger.error(f"Malformed action item: '{item}'. Removing.")
                continue
            name, action, params, added_time = parsed

            # Only process actions for this thread, or clean up for missing threads
            if name == self.t_name:
                self.logger.debug(f'{self.t_name}: Processing action "{action}" with params "{params}".')
                base_action = action.split('_', 1)[0]
                action_handler = self._action_handlers.get(base_action)
                if not action_handler:
                    self.logger.error(f'{self.t_name}: Unknown action command "{action}".')
                    continue
                try:
                    if base_action in ['shot', 'info']:
                        action_handler(frame, params, frame_count)
                    elif base_action in ['multicast', 'host']:
                        action_handler(params)
                    else:
                        action_handler(params)
                except Exception as exc:
                    self.logger.error(
                        f"Error executing action '{action}' for {self.t_name} with {exc}:\n{traceback.format_exc()}")
                # Do not add to new_todo (processed)
            elif name not in self.class_obj.cast_names:
                self.logger.warning(f"Removing action for non-existent cast name: {name}")
                continue
            else:
                # Keep actions for other threads
                new_todo.append(item)

        # Atomically update the to-do list
        self.class_obj.cast_name_todo = new_todo

        return self.t_todo_stop, self.t_preview, self.frame_buffer, self.cast_frame_buffer, self.class_obj.cast_name_todo

    # --- Static Methods ---

    @staticmethod
    def get_available_actions():
        """Returns a list of all available action keys."""
        return list(ActionExecutor._ACTION_HANDLERS_MAP.keys())