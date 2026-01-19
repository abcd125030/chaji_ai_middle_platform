'use client';

import ReactPlayer from 'react-player';
import React from 'react';

const VideoPlayer = (props: React.ComponentProps<typeof ReactPlayer>) => {
  return <ReactPlayer {...props} />;
};

export default VideoPlayer;