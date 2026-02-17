import json
from urllib.parse import urlparse, parse_qs, urlencode
from urllib.request import urlopen
from typing import Optional, List

from fastapi import HTTPException
from youtube_transcript_api import YouTubeTranscriptApi

class YouTubeTools:
    @staticmethod
    def get_youtube_video_id(url: str) -> Optional[str]:
        """Function to get the video ID from a YouTube URL."""
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname

        if hostname == "youtu.be":
            return parsed_url.path[1:]
        if hostname in ("www.youtube.com", "youtube.com"):
            if parsed_url.path == "/watch":
                query_params = parse_qs(parsed_url.query)
                return query_params.get("v", [None])[0]
            if parsed_url.path.startswith("/embed/"):
                return parsed_url.path.split("/")[2]
            if parsed_url.path.startswith("/v/"):
                return parsed_url.path.split("/")[2]
        return None

    @staticmethod
    def get_video_data(url: str) -> dict:
        """Function to get video data from a YouTube URL."""
        if not url:
            raise HTTPException(status_code=400, detail="No URL provided")

        try:
            video_id = YouTubeTools.get_youtube_video_id(url)
            if not video_id:
                raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        except Exception:
            raise HTTPException(status_code=400, detail="Error getting video ID from URL")

        try:
            params = {"format": "json", "url": f"https://www.youtube.com/watch?v={video_id}"}
            oembed_url = "https://www.youtube.com/oembed"
            query_string = urlencode(params)
            full_url = oembed_url + "?" + query_string

            with urlopen(full_url) as response:
                response_text = response.read()
                video_data = json.loads(response_text.decode())
                clean_data = {
                    "title": video_data.get("title"),
                    "author_name": video_data.get("author_name"),
                    "author_url": video_data.get("author_url"),
                    "type": video_data.get("type"),
                    "height": video_data.get("height"),
                    "width": video_data.get("width"),
                    "version": video_data.get("version"),
                    "provider_name": video_data.get("provider_name"),
                    "provider_url": video_data.get("provider_url"),
                    "thumbnail_url": video_data.get("thumbnail_url"),
                }
                return clean_data
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting video data: {str(e)}")

    @staticmethod
    def get_video_captions(url: str, languages: Optional[List[str]] = None) -> str:
        """Get captions from a YouTube video."""
        if not url:
            raise HTTPException(status_code=400, detail="No URL provided")

        try:
            video_id = YouTubeTools.get_youtube_video_id(url)
            if not video_id:
                raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        except Exception:
            raise HTTPException(status_code=400, detail="Error getting video ID from URL")

        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            captions = None
            
            if languages:
                # Try to find transcript in specified languages
                try:
                    transcript = transcript_list.find_transcript(languages)
                    captions = transcript.fetch()
                except Exception:
                    # If exact match not found, try each language individually
                    for lang in languages:
                        try:
                            transcript = transcript_list.find_transcript([lang])
                            captions = transcript.fetch()
                            break
                        except Exception:
                            continue
                    
                    # If still not found, try to translate from any available transcript
                    if not captions:
                        try:
                            for transcript in transcript_list:
                                if transcript.is_translatable:
                                    translated = transcript.translate(languages[0])
                                    captions = translated.fetch()
                                    break
                        except Exception:
                            pass
            else:
                # Try to get transcript in English first, then any available
                try:
                    transcript = transcript_list.find_generated_transcript(['en'])
                    captions = transcript.fetch()
                except Exception:
                    try:
                        transcript = transcript_list.find_manually_created_transcript(['en'])
                        captions = transcript.fetch()
                    except Exception:
                        # Get any available transcript
                        for transcript in transcript_list:
                            captions = transcript.fetch()
                            break
            
            if captions:
                return " ".join(line["text"] for line in captions)
            return "No captions found for video"
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting captions for video: {str(e)}")

    @staticmethod
    def get_video_timestamps(url: str, languages: Optional[List[str]] = None) -> List[str]:
        """Generate timestamps for a YouTube video based on captions."""
        if not url:
            raise HTTPException(status_code=400, detail="No URL provided")

        try:
            video_id = YouTubeTools.get_youtube_video_id(url)
            if not video_id:
                raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        except Exception:
            raise HTTPException(status_code=400, detail="Error getting video ID from URL")

        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            captions = None
            target_languages = languages or ["en"]
            
            # Try to find transcript in specified languages
            try:
                transcript = transcript_list.find_transcript(target_languages)
                captions = transcript.fetch()
            except Exception:
                # If exact match not found, try each language individually
                for lang in target_languages:
                    try:
                        transcript = transcript_list.find_transcript([lang])
                        captions = transcript.fetch()
                        break
                    except Exception:
                        continue
                
                # If still not found, try to get any available transcript
                if not captions:
                    try:
                        transcript = transcript_list.find_generated_transcript(target_languages)
                        captions = transcript.fetch()
                    except Exception:
                        try:
                            transcript = transcript_list.find_manually_created_transcript(target_languages)
                            captions = transcript.fetch()
                        except Exception:
                            # Get any available transcript
                            for transcript in transcript_list:
                                captions = transcript.fetch()
                                break
            
            if not captions:
                raise HTTPException(status_code=404, detail="No captions found for video")
            
            timestamps = []
            for line in captions:
                start = int(line["start"])
                minutes, seconds = divmod(start, 60)
                timestamps.append(f"{minutes}:{seconds:02d} - {line['text']}")
            return timestamps
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating timestamps: {str(e)}")