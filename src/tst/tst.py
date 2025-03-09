import av

av.logging.set_level(av.logging.VERBOSE)

input_ = av.open("0", format="avfoundation", options={'probesize':'100M'})
output = av.open("out.mkv", "w")

output_stream = output.add_stream("h264", rate=30)
output_stream.width = input_.streams.video[0].width
output_stream.height = input_.streams.video[0].height
output_stream.pix_fmt = "yuv420p"

try:
    while True:
        try:
            for frame in input_.decode(video=0):
                packet = output_stream.encode(frame)
                output.mux(packet)
        except av.BlockingIOError:
            pass
except KeyboardInterrupt:
    print("Recording stopped by user")

packet = output_stream.encode(None)
output.mux(packet)

input_.close()
output.close()

packet = output_stream.encode(None)
output.mux(packet)

input_.close()
output.close()
