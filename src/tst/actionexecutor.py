"""
# a: zak-45
# d: 01/10/2024
# v: 1.0.0
#
# Action  Utils
#
#          CAST utilities
#
#
"""
import traceback

from src.utl.cv2utils import CV2Utils, ImageUtils
from src.net.ddp_queue import DDPDevice
from str2bool import str2bool
from threading import current_thread

class ActionExecutor:
    def __init__(self, class_obj, logger, **kwargs):
        """
        Initializes the ActionExecutor with the necessary context for executing actions.

        Args:
            class_obj: The instance of the casting class (e.g., CASTDesktop).
            logger: The logger instance for logging messages.
            **kwargs: A dictionary containing the execution context (frame, t_name, etc.).
        """
        self.class_obj = class_obj
        self.logger = logger

        # Unpack and store the execution context from kwargs
        self.frame = kwargs.get('frame')
        self.t_name = kwargs.get('t_name')
        self.t_viinput = kwargs.get('t_viinput')
        self.t_scale_width = kwargs.get('t_scale_width')
        self.t_scale_height = kwargs.get('t_scale_height')
        self.t_multicast = kwargs.get('t_multicast')
        self.ip_addresses = kwargs.get('ip_addresses')
        self.ddp_host = kwargs.get('ddp_host')
        self.t_cast_x = kwargs.get('t_cast_x')
        self.t_cast_y = kwargs.get('t_cast_y')
        self.start_time = kwargs.get('start_time')
        self.t_preview = kwargs.get('t_preview')
        self.fps = kwargs.get('fps')
        self.frame_count = kwargs.get('frame_count')
        self.media_length = kwargs.get('media_length')
        self.swapper = kwargs.get('swapper')
        self.shared_buffer = kwargs.get('shared_buffer')
        self.frame_buffer = kwargs.get('frame_buffer')
        self.cast_frame_buffer = kwargs.get('cast_frame_buffer')
        self.t_protocol = kwargs.get('t_protocol')

        self.action_handlers = {
            'stop': self.handle_stop_action,
            'shot': self.handle_snapshot_action,
            'info': self.handle_info_action,
            'reset': self.handle_reset_action,
            'host': self.handle_host_action,
            'multicast': self.handle_multicast_action,
            'close-preview': self.handle_close_preview,
            'open-preview': self.handle_open_preview,
        }


    def execute_actions(self, t_todo_stop):
        """
        Executes actions for a video processing thread.

        Args:
            t_todo_stop (bool): Stop flag.

        Returns:
            tuple: Updated t_todo_stop and self.t_preview flags.
        """

        for item in list(self.class_obj.cast_name_todo): # Iterate over a copy to avoid issues with removing items
            name, action, params, added_time = item.split('||')

            if name not in self.class_obj.cast_names:
                self.class_obj.cast_name_todo.remove(item)
                continue

            if name == self.t_name:
                self.logger.debug(f'To do: {action} for :{self.t_name}')

                try:
                    action_key = action.split('_')[0]
                    if action_handler := self.action_handlers.get(action_key):
                        # Call the handler. It will use the instance attributes for context.
                        # We only need to pass the action-specific 'params'.
                        result = action_handler(params)
                        # Update state based on handler result if necessary
                        if action_key == 'stop':
                            t_todo_stop = result
                        elif action_key in ['open-preview', 'close-preview']:
                            self.t_preview = result
                    else:
                        self.logger.error(f'Unknown action: {action}')
                except Exception as error:
                    self.logger.error(traceback.format_exc())
                    self.logger.error(f'Action {action} in ERROR from {self.t_name} : {error}')

                finally:
                    self.class_obj.cast_name_todo.remove(item)

        return t_todo_stop, self.t_preview

    def handle_snapshot_action(self, params):
        add_frame = CV2Utils.pixelart_image(self.frame, self.t_scale_width, self.t_scale_height)
        add_frame = CV2Utils.resize_image(add_frame, self.t_scale_width, self.t_scale_height)
        if self.t_multicast:
            add_frame = CV2Utils.resize_image(self.frame, self.t_scale_width * self.t_cast_x, self.t_scale_height * self.t_cast_y)

        self.frame_buffer.append(add_frame)

    def handle_info_action(self, params):
        if str(self.t_viinput) != "queue":
            img = ImageUtils.image_array_to_base64(self.frame) if str2bool(params) else "None"
        else:
            img = "None"
        t_info = {self.t_name: {
            "type": "info",
            "data": {
                "start": self.start_time,
                "cast_type": self.class_obj.__name__,
                "tid": current_thread().native_id,
                "viinput": str(self.t_viinput),
                "preview": self.t_preview,
                "protocol": self.t_protocol,
                "multicast": self.t_multicast,
                "devices": self.ip_addresses,
                "image": {
                    "W": self.t_scale_width,
                    "H": self.t_scale_height
                },
                "fps": self.fps,
                "frames": self.frame_count,
                "length": self.media_length,
                "img": img
            }
        }}
        self.shared_buffer.put(t_info)
        self.logger.debug(f'{self.t_name} info put in shared buffer')

    def handle_multicast_action(self, params):
        if not self.t_multicast:
            self.logger.warning(f'{self.t_name} Not multicast cast')
            return

        try:
            if params == 'stop':
                action_arg = 'stop'
                delay_arg = 0
            else:
                action_arg, delay_arg = params.split(',')
                delay_arg = int(delay_arg)
        except ValueError:
            self.logger.error(f'{self.t_name} Invalid multicast params: {params}')
            return


        if self.swapper.running and action_arg != 'stop':
            self.logger.warning(f'{self.t_name} Already a running effect')
            return

        if action_arg == 'circular':
            self.swapper.start_circular_swap(delay_arg)
        elif action_arg == 'reverse':
            self.swapper.start_reverse_swap(delay_arg)
        elif action_arg == 'random':
            self.swapper.start_random_order(delay_arg)
        elif action_arg == 'pause':
            self.swapper.start_random_replace(delay_arg)
        elif action_arg == 'stop':
            self.swapper.stop()
        else:
            self.logger.error(f'{self.t_name} Unknown Multicast action: {params}')

    def handle_host_action(self, params):
        self.ip_addresses[0] = params
        if self.ddp_host:
            self.ddp_host._destination = params
        else:
            DDPDevice(params)

    def handle_reset_action(self, params):
        self.class_obj.total_frames = 0
        self.class_obj.total_packets = 0
        self.class_obj.reset_total = False

    def handle_close_preview(self, params):
        """Handles the 'close-preview' action."""
        CV2Utils.cv2_win_close(str(self.class_obj.server_port), self.class_obj.__class__.__name__, self.t_name, self.t_viinput)
        return False  # Return the new state for t_preview

    def handle_open_preview(self, params):
        """Handles the 'open-preview' action."""
        return True  # Return the new state for t_preview

    def handle_stop_action(self, params):
        """Handles the 'stop' action."""
        return True
