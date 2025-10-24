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
    def __init__(self, class_obj, logger):
        self.class_obj = class_obj
        self.logger = logger
        self.action_handlers = {
            'stop': self.handle_stop_action,
            'shot': self.handle_snapshot_action,
            'info': self.handle_info_action,
            'reset': self.handle_reset_action,
            'host': self.handle_host_action,
            'multicast': self.handle_multicast_action,
            'close-preview': lambda: self.handle_preview_control('close-preview'),
            'open-preview': lambda: self.handle_preview_control('open-preview'),
        }


    def execute_actions(self,
                        frame,
                        t_name,
                        t_viinput,
                        t_scale_width,
                        t_scale_height,
                        t_multicast,
                        ip_addresses,
                        ddp_host,
                        t_cast_x,
                        t_cast_y,
                        start_time,
                        t_todo_stop,
                        t_preview,
                        fps,
                        frame_count,
                        media_length,
                        swapper,
                        shared_buffer,
                        frame_buffer,
                        cast_frame_buffer,
                        t_protocol):
        """
        Executes actions for a video processing thread.

        Args:
            t_protocol (str): Protocol used to stream data.
            frame (np.ndarray): Current image frame.
            t_name (str): Thread name.
            t_viinput (str): Video input source.
            t_scale_width (int): Width for scaling.
            t_scale_height (int): Height for scaling.
            t_multicast (bool): Multicast flag.
            ip_addresses (list): List of IP addresses.
            ddp_host (DDPDevice): DDP device instance.
            t_cast_x (int): Cast X coordinate.
            t_cast_y (int): Cast Y coordinate.
            start_time (float): Start time.
            t_todo_stop (bool): Stop flag.
            t_preview (bool): Preview flag.
            fps (float): Frames per second.
            frame_count (int): Frame count.
            media_length (float): Length of the media.
            swapper (object): Swapper instance.
            shared_buffer (queue.Queue): Shared buffer queue.
            frame_buffer (list): Frame buffer.
            cast_frame_buffer (list): Cast frame buffer.

        Returns:
            tuple: Updated t_todo_stop and t_preview flags.
        """

        for item in list(self.class_obj.cast_name_todo): # Iterate over a copy to avoid issues with removing items
            name, action, params, added_time = item.split('||')

            if name not in self.class_obj.cast_names:
                self.class_obj.cast_name_todo.remove(item)
                continue

            if name == t_name:
                self.logger.debug(f'To do: {action} for :{t_name}')

                try:
                    if action_handler := self.action_handlers.get(
                        action.split('_')[0]
                    ):
                        action_handler(frame, t_name, t_viinput, t_scale_width, t_scale_height, t_multicast, ip_addresses,
                                        ddp_host, t_cast_x, t_cast_y, start_time, t_preview, fps, frame_count,
                                        media_length, swapper, shared_buffer, frame_buffer, cast_frame_buffer, params, t_protocol)
                    else:
                        self.logger.error(f'Unknown action: {action}')
                except Exception as error:
                    self.logger.error(traceback.format_exc())
                    self.logger.error(f'Action {action} in ERROR from {t_name} : {error}')

                self.class_obj.cast_name_todo.remove(item)

        return t_todo_stop, t_preview

    def handle_snapshot_action(self, *args):
        frame, t_scale_width, t_scale_height, t_multicast, t_cast_x, t_cast_y, frame_buffer = args[0], args[4], args[5], args[6], args[8], args[9], args[-3]
        add_frame = CV2Utils.pixelart_image(frame, t_scale_width, t_scale_height)
        add_frame = CV2Utils.resize_image(add_frame, t_scale_width, t_scale_height)
        if t_multicast:
            add_frame = CV2Utils.resize_image(frame, t_scale_width * t_cast_x, t_scale_height * t_cast_y)

        frame_buffer.append(add_frame)

    def handle_info_action(self, *args):
        frame, t_name, t_viinput, t_scale_width, t_scale_height, start_time, t_preview, fps, frame_count, media_length, shared_buffer, ip_addresses, params, t_protocol = args[0], args[1], args[2], args[4], args[5], args[10], args[12], args[13], args[14], args[15], args[-4], args[7], args[-2], args[-1]

        if str(t_viinput) != "queue":
            img = ImageUtils.image_array_to_base64(frame) if str2bool(params) else "None"
        else:
            img = "None"
        t_info = {t_name: {
            "type": "info",
            "data": {
                "start": start_time,
                "cast_type": self.class_obj.__name__,
                "tid": current_thread().native_id,
                "viinput": str(t_viinput),
                "preview": t_preview,
                "protocol": t_protocol,
                "multicast": args[6],
                "devices": ip_addresses,
                "image": {
                    "W": t_scale_width,
                    "H": t_scale_height
                },
                "fps": fps,
                "frames": frame_count,
                "length": media_length,
                "img": img
            }
        }}
        shared_buffer.put(t_info)
        self.logger.debug(f'{t_name} info put in shared buffer')

    def handle_multicast_action(self, *args):
        t_name, t_multicast, swapper, logger, params = args[1], args[6], args[-5], args[-6], args[-2]
        if not t_multicast:
            logger.warning(f'{t_name} Not multicast cast')
            return

        try:
            if params == 'stop':
                action_arg = 'stop'
                delay_arg = 0
            else:
                action_arg, delay_arg = params.split(',')
                delay_arg = int(delay_arg)
        except ValueError:
            logger.error(f'{t_name} Invalid multicast params: {params}')
            return


        if swapper.running and action_arg != 'stop':
            logger.warning(f'{t_name} Already a running effect')
            return

        if action_arg == 'circular':
            swapper.start_circular_swap(delay_arg)
        elif action_arg == 'reverse':
            swapper.start_reverse_swap(delay_arg)
        elif action_arg == 'random':
            swapper.start_random_order(delay_arg)
        elif action_arg == 'pause':
            swapper.start_random_replace(delay_arg)
        elif action_arg == 'stop':
            swapper.stop()
        else:
            logger.error(f'{t_name} Unknown Multicast action: {params}')

    def handle_host_action(self, *args):
        ip_addresses, ddp_host, params = args[7], args[8], args[-2]
        ip_addresses[0] = params
        if ddp_host:
            ddp_host._destination = params
        else:
            DDPDevice(params)

    def handle_reset_action(self, *args):
        self.class_obj.total_frames = 0
        self.class_obj.total_packets = 0
        self.class_obj.reset_total = False

    def handle_preview_control(self, t_action, *args):
        class_obj, t_name, t_viinput, t_preview = args[-7], args[1], args[2], args[12]

        if t_action == 'close-preview':
            CV2Utils.cv2_win_close(str(class_obj.server_port), class_obj.__class__.__name__, t_name, t_viinput)
            return False
        elif t_action == 'open-preview':
            return True
        return t_preview

    def handle_stop_action(self, *args):
        return True

