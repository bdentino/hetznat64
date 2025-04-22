#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/if.h>
#include <linux/if_tun.h>
#include <errno.h>

int configure_tun(const char *iface_name)
{
  struct ifreq ifr;
  int fd, err;

  // Open the TUN device file
  if ((fd = open("/dev/net/tun", O_RDWR)) < 0)
  {
    perror("Opening /dev/net/tun failed");
    return fd;
  }

  // Prepare the flags
  memset(&ifr, 0, sizeof(ifr));
  ifr.ifr_flags = IFF_TUN | IFF_NO_PI | IFF_MULTI_QUEUE;

  if (*iface_name)
    strncpy(ifr.ifr_name, iface_name, IFNAMSIZ);

  // Call ioctl to set the device configuration
  if ((err = ioctl(fd, TUNSETIFF, (void *)&ifr)) < 0)
  {
    perror("ioctl TUNSETIFF");
    close(fd);
    return err;
  }

  printf("Assigned interface: %s\n", ifr.ifr_name);
  return fd;
}

int main(int argc, char *argv[])
{
  if (argc != 2)
  {
    fprintf(stderr, "Usage: %s <interface-name>\n", argv[0]);
    return 1;
  }

  int fd = configure_tun(argv[1]);
  if (fd >= 0)
  {
    printf("TUN interface configured successfully.\n");
    close(fd);
  }

  return 0;
}
