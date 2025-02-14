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

def execute_actions(class_obj,
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
                    interval,
                    frame_count,
                    media_length,
                    swapper,
                    shared_buffer,
                    frame_buffer,
                    cast_frame_buffer,
                    logger,
                    t_protocol):
    """
    Logic for action thread that need to execute (Desktop or Media)

    :param t_protocol: protocol used to stream ddata
    :param class_obj: Media or Desktop
    :param frame: Current image frame
    :param t_name: Thread name
    :param t_viinput: Video input
    :param t_scale_width: Width for scaling
    :param t_scale_height: Height for scaling
    :param t_multicast: Multicast flag
    :param ip_addresses: List of IP addresses
    :param ddp_host: DDP device instance
    :param t_cast_x: Cast X coordinate
    :param t_cast_y: Cast Y coordinate
    :param start_time: Start time
    :param t_todo_stop: Stop flag
    :param t_preview: Preview flag
    :param interval: FPS
    :param frame_count: Frame count
    :param media_length: Length of the media
    :param swapper: Swapper instance
    :param shared_buffer: Shared buffer queue
    :param frame_buffer: Frame buffer
    :param cast_frame_buffer: Cast frame buffer
    :param logger: Logger handler
    :return: Updated t_todo_stop and t_preview flags
    """

    def handle_snapshot_action():
        add_frame = CV2Utils.pixelart_image(frame, t_scale_width, t_scale_height)
        add_frame = CV2Utils.resize_image(add_frame, t_scale_width, t_scale_height)
        if t_multicast:
            add_frame = CV2Utils.resize_image(frame, t_scale_width * t_cast_x, t_scale_height * t_cast_y)

        frame_buffer.append(add_frame)

    def handle_info_action():
        if str(t_viinput) != "queue":
            img = ImageUtils.image_array_to_base64(frame) if str2bool(params) else "None"
        else:
            img = "None"
        t_info = {t_name: {
            "type": "info",
            "data": {
                "start": start_time,
                "cast_type": class_obj.__name__,
                "tid": current_thread().native_id,
                "viinput": str(t_viinput),
                "preview": t_preview,
                "protocol": t_protocol,
                "multicast": t_multicast,
                "devices": ip_addresses,
                "image": {
                    "W": t_scale_width,
                    "H": t_scale_height
                },
                "fps": interval,
                "frames": frame_count,
                "length": media_length,
                "img": img
            }
        }}
        shared_buffer.put(t_info)
        logger.debug(f'{t_name} info put in shared buffer')

    def handle_multicast_action():
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

    def handle_host_action(t_ddp_host):
        ip_addresses[0] = params
        if t_ddp_host:
            t_ddp_host._destination = params
        else:
            DDPDevice(params)

    def handle_reset_action():
        class_obj.total_frame = 0
        class_obj.total_packet = 0
        class_obj.reset_total = False

    def handle_preview_control(t_action):
        nonlocal t_preview
        if t_action == 'close-preview':
            CV2Utils.cv2_win_close(str(class_obj.server_port), class_obj.__class__.__name__, t_name, t_viinput)
            t_preview = False
        elif t_action == 'open-preview':
            t_preview = True

    def handle_stop_action():
        nonlocal t_todo_stop
        t_todo_stop = True

    action_handlers = {
        'stop': handle_stop_action,
        'shot': handle_snapshot_action,
        'info': handle_info_action,
        'reset': handle_reset_action,
        'host': lambda: handle_host_action(ddp_host),
        'multicast': handle_multicast_action,
        'close-preview': lambda: handle_preview_control('close-preview'),
        'open-preview': lambda: handle_preview_control('open-preview'),
    }

    for item in class_obj.cast_name_todo:
        name, action, params, added_time = item.split('||')

        if name not in class_obj.cast_names:
            class_obj.cast_name_todo.remove(item)
            continue

        if name == t_name:
            logger.debug(f'To do: {action} for :{t_name}')

            try:
                action_handler = action_handlers.get(action.split('_')[0])
                if action_handler:
                    action_handler()
                else:
                    logger.error(f'Unknown action: {action}')
            except Exception as error:
                logger.error(traceback.format_exc())
                logger.error(f'Action {action} in ERROR from {t_name} : {error}')

            class_obj.cast_name_todo.remove(item)

    return t_todo_stop, t_preview
