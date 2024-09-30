"""
# a: zak-45
# d: 01/10/2024
# v: 1.0.0
#
# Action Utility
# code shared by Desktop & Media
#
"""
from cv2utils import CV2Utils
from utils import CASTUtils as Utils
from ddp_queue import DDPDevice
import threading
import traceback
from cv2utils import ImageUtils
from str2bool import str2bool


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
                    logger):
    """    
    Logic for action thread need to execute (Desktop or Media)

    :param cast_frame_buffer:
    :param frame_buffer:
    :param t_scale_height:
    :param t_scale_width:
    :param t_todo_stop:
    :param media_length:
    :param frame_count:
    :param interval:
    :param t_preview:
    :param start_time:
    :param t_cast_y:
    :param t_cast_x:
    :param t_viinput:
    :param ip_addresses:
    :param frame:
    :param t_multicast:
    :param ddp_host: DDP device instance
    :param swapper: swap IP instance
    :param shared_buffer: Queue
    :param t_name: Thread name
    :param logger: logger handler
    :param class_obj: Media or Desktop
    :return: 
    """
    #  take thread name from cast to do list
    for item in class_obj.cast_name_todo:
        name, action, params, added_time = item.split('||')

        # if the action from the list is for an unknown thread, clean up
        if name not in class_obj.cast_names:
            class_obj.cast_name_todo.remove(item)
    
        # action is for this thread
        elif name == t_name:
            logger.debug(f'To do: {action} for :{t_name}')
    
            # use try to capture any failure
            try:
                # Main logic by action type

                # stop the thread
                if 'stop' in action:
                    t_todo_stop = True

                # take a snapshot and store into BUFFER
                elif 'shot' in action:
                    add_frame = CV2Utils.pixelart_image(frame, t_scale_width, t_scale_height)
                    add_frame = CV2Utils.resize_image(add_frame, t_scale_width, t_scale_height)
                    frame_buffer.append(add_frame)
                    if t_multicast:
                        # resize frame to virtual matrix size
                        add_frame = CV2Utils.resize_image(frame,
                                                          t_scale_width * t_cast_x,
                                                          t_scale_height * t_cast_y)
    
                        cast_frame_buffer.append(Utils.split_image_to_matrix(add_frame, t_cast_x, t_cast_y))

                # put thread info into the Queue to be read by calling func
                elif 'info' in action:
                    img = None
                    if str2bool(params):
                        img = ImageUtils.image_array_to_base64(frame)
                    t_info = {t_name: {"type": "info", "data": {"start": start_time,
                                                                "cast_type": class_obj.__name__,
                                                                "tid": threading.current_thread().native_id,
                                                                "viinput": str(t_viinput),
                                                                "preview": t_preview,
                                                                "multicast": t_multicast,
                                                                "devices": ip_addresses,
                                                                "image":{
                                                                "W": t_scale_width,
                                                                "H": t_scale_height
                                                                },
                                                                "fps": 1 / interval,
                                                                "frames": frame_count,
                                                                "length": media_length,
                                                                "img": img
                                                                }
                                       }
                              }
                    # this wait until queue access is free
                    shared_buffer.put(t_info)
                    logger.debug(f'{t_name} we have put')

                # close preview window
                elif 'close_preview' in action:
                    CV2Utils.cv2_win_close(str(class_obj.server_port), class_obj.__name__, t_name, t_viinput)
                    t_preview = False

                # run preview window
                elif 'open_preview' in action:
                    t_preview = True

                # reset some monitoring values
                elif "reset" in action:
                    class_obj.total_frame = 0
                    class_obj.total_packet = 0
                    class_obj.reset_total = False

                # this will update first IP address, usually coming from self.host
                elif "host" in action:
                    ip_addresses[0] = params
                    if ddp_host is not None:
                        ddp_host._destination = params
                    else:
                        ddp_host = DDPDevice(params)

                # apply multicast effects
                elif "multicast" in action:
                    if t_multicast:
                        if t_multicast:
                            if params == 'stop':
                                swapper.stop()
                            else:
                                action_arg, delay_arg = params.split(',')
                                delay_arg = int(delay_arg)
                                if swapper.running:
                                    logger.warning(f'{t_name} Already a running effect')
                                else:
                                    if action_arg == 'circular':
                                        swapper.start_circular_swap(delay_arg)
                                    elif action_arg == 'reverse':
                                        swapper.start_reverse_swap(delay_arg)
                                    elif action_arg == 'random':
                                        swapper.start_random_order(delay_arg)
                                    elif action_arg == 'pause':
                                        swapper.start_random_replace(delay_arg)
                                    else:
                                        logger.error(f'{t_name} Unknown Multicast action e.g random,1000 : {params}')
                    else:
                        logger.error(f'{t_name} Not multicast cast')
    
            except Exception as error:
                logger.error(traceback.format_exc())
                logger.error(f'Action {action} in ERROR from {t_name} : {error}')

            # once action finished, remove it from the list
            class_obj.cast_name_todo.remove(item)

    return t_todo_stop, t_preview