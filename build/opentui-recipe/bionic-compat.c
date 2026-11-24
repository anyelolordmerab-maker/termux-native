
/* musl/bionic: __errno_location no existe en bionic; lo provee own stub. */
int *__errno_location(void) { return &errno; }
