import av

frame_count = 0
frame_interval = 25
input_format = 'gdigrab'
t_viinput = 'title=Audacity'  # 'desktop' full screen or 'title=<window title>'

# Open video device (desktop / window)
input_options = {'c:v': 'libx264rgb', 'crf': '0', 'preset': 'ultrafast', 'pix_fmt': 'rgb24',
                 'framerate': str(frame_interval), 'probesize': '100M'}

# Open av input container in read mode
try:

    input_container = av.open(t_viinput, 'r', format=input_format, options=input_options)

except Exception as error:
    print(f'An exception occurred: {error}')

try:

    # Output video in case of UDP or other
    output_options = {}
    output_format = 'matroska'
    output_filename = 'test.mkv'

    output_container = av.open(output_filename, 'w', format=output_format)
    output_stream = output_container.add_stream('h264', rate=25, options=output_options)

except Exception as error:
    print(f'An exception occurred: {error}')

if input_container:
    # input video stream from container (for decode)
    input_stream = input_container.streams.get(video=0)

    # Main frame loop
    # Stream loop
    try:

        for frame in input_container.decode(input_stream):

            frame_count += 1
            print(frame_count)
            if output_container:
                # we send frame to output only if it exists, here only for test, this bypass ddp etc ...
                # Encode the frame
                packets = output_stream.encode(frame)
                # Mux the encoded packet
                for packet in packets:
                    if packet.dts is None:
                        continue
                    output_container.mux(packet)

    except Exception as error:
        print(error)
