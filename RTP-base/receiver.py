import argparse
import io
import socket
import sys
from utils import PacketHeader, compute_checksum


def receiver(receiver_ip, receiver_port, window_size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((receiver_ip, receiver_port))

    msg_buffer = io.BytesIO()

    packet_buffer = {}

    started = False
    while not started:
        pkt, address = s.recvfrom(2048)
        header = PacketHeader(pkt[:16])
        if header.type == 0 and header.seq_num == 0:
            start_ack = PacketHeader(type=3, seq_num=1, length=0)
            start_ack.checksum = compute_checksum(start_ack)
            s.sendto(bytes(start_ack), address)
            started = True

    expected_seq_num = 0
    while True:
        pkt, address = s.recvfrom(2048)
        header = PacketHeader(pkt[:16])
        msg = pkt[16: 16 + header.length]
        checksum = header.checksum
        header.checksum = 0
        computed_checksum = compute_checksum(header / msg)
        if checksum != computed_checksum:
            continue

        if header.type == 1:
            ack_pkt = PacketHeader(type=3, seq_num=expected_seq_num + 1, length=0)
            ack_pkt.checksum = compute_checksum(ack_pkt)
            s.sendto(bytes(ack_pkt), address)

            full_message = msg_buffer.getvalue()
            sys.stdout.buffer.write(full_message)
            sys.stdout.buffer.flush()
            break

        elif header.type == 2:
            if header.seq_num < expected_seq_num:
                ack_pkt = PacketHeader(type=3, seq_num=expected_seq_num, length=0)
                ack_pkt.checksum = compute_checksum(ack_pkt)
                s.sendto(bytes(ack_pkt), address)
            elif expected_seq_num < header.seq_num < expected_seq_num + window_size:
                if header.seq_num not in packet_buffer:
                    packet_buffer[header.seq_num] = msg
                ack_pkt = PacketHeader(type=3, seq_num=expected_seq_num, length=0)
                ack_pkt.checksum = compute_checksum(ack_pkt)
                s.sendto(bytes(ack_pkt), address)
            elif header.seq_num == expected_seq_num:
                msg_buffer.write(bytes(msg))
                expected_seq_num += 1
                while expected_seq_num in packet_buffer:
                    msg_buffer.write(packet_buffer[expected_seq_num])
                    packet_buffer.pop(expected_seq_num)
                    expected_seq_num += 1
                ack_pkt = PacketHeader(type=3, seq_num=expected_seq_num, length=0)
                ack_pkt.checksum = compute_checksum(ack_pkt)
                s.sendto(bytes(ack_pkt), address)


    s.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "receiver_ip", help="The IP address of the host that receiver is running on"
    )
    parser.add_argument(
        "receiver_port", type=int, help="The port number on which receiver is listening"
    )
    parser.add_argument(
        "window_size", type=int, help="Maximum number of outstanding packets"
    )
    args = parser.parse_args()

    receiver(args.receiver_ip, args.receiver_port, args.window_size)


if __name__ == "__main__":
    main()
