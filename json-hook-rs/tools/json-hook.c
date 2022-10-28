#include <stdlib.h>
#include <stdio.h>
#include <sys/socket.h>
#include <unistd.h>

#define APT_HOOK_SOCKET "APT_HOOK_SOCKET"

char buf[1024];

int main(void)
{
    char *fd = getenv(APT_HOOK_SOCKET);
    if (fd == NULL) {
        printf("APT_HOOK_SOCKET not found");
        return 1;
    }

    int sfd = dup(atoi(fd));
    printf("fd: %s\nsfd: %d\n", fd, sfd);

    if( recv(sfd, (void *) *buf, 1024, 0) < 0)
	{
		puts("recv failed");
        return 1;
	}

    puts("Reply received\n");
	puts(buf);

    // int sfd = socket(AF_UNIX, SOCK_STREAM, 0);
    // if (sfd == -1) {
    //     printf("sfd\n");
    //     return 1;
    // }

    return 0;
}


