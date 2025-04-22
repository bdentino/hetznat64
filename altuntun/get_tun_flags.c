#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/if.h>
#include <linux/if_tun.h>

int get_tun_flags(const char *iface_name)
{
  struct ifreq ifr;
  int fd, err;

  // Open the control interface for all network interfaces
  fd = socket(AF_INET, SOCK_DGRAM, 0);
  if (fd < 0)
  {
    perror("Opening socket failed");
    return fd;
  }

  // Prepare the ifreq structure
  memset(&ifr, 0, sizeof(ifr));
  if (strlen(iface_name) >= IFNAMSIZ)
  {
    fprintf(stderr, "Interface name is too long\n");
    close(fd);
    return -1;
  }

  strncpy(ifr.ifr_name, iface_name, IFNAMSIZ);

  // Request the flags with ioctl
  err = ioctl(fd, SIOCGIFFLAGS, &ifr);
  if (err < 0)
  {
    perror("ioctl SIOCGIFFLAGS");
    close(fd);
    return err;
  }

  close(fd);

  // Print the flags
  printf("Flags for %s: 0x%x\n", iface_name, ifr.ifr_flags);

  // Return the flags
  return ifr.ifr_flags;
}

int main(int argc, char *argv[])
{
  if (argc != 2)
  {
    fprintf(stderr, "Usage: %s <interface-name>\n", argv[0]);
    return 1;
  }

  int flags = get_tun_flags(argv[1]);
  if (flags >= 0)
  {
    printf("Successfully got flags for the TUN device.\n");
  }
  else
  {
    printf("Failed to get flags for the TUN device.\n");
  }

  return 0;
}
