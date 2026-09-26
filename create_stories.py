import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from django.contrib.auth.models import User
from django.core.files import File
from apps.stories.models import Story, StoryChapter, StoryTag
author = User.objects.first()
data = [
    {
        "title": "Manchester City Secure Dramatic Win in Final Minutes",
        "content": "A late goal in the 89th minute secured all three points for the home side in an intense contest.",
        "tag_name": "Premier League",
        "image": "story1.jpg",
    },
    {
        "title": "Transfer News: Top Striker Set to Join New Club",
        "content": "Reports suggest a major transfer deal is close to being finalized this summer window.",
        "tag_name": "Transfer",
        "image": "story2.jpg",
    },
    {
        "title": "Preview: Key Fixture This Weekend in the League",
        "content": "Fans are eagerly awaiting this weekend's big match between two title contenders.",
        "tag_name": "Premier League",
        "image": "story3.jpg",
    },
    {
        "title": "Champions League Draw Announced for Next Round",
        "content": "The draw for the next stage has been completed, setting up several exciting fixtures.",
        "tag_name": "Champions League",
        "image": "story4.jpg",
    },
    {
        "title": "Star Midfielder Returns From Injury Ahead of Derby",
        "content": "The club's key player is back in training and could feature in the upcoming derby match.",
        "tag_name": "Serie A",
        "image": "story5.jpg",
    },
    {
        "title": "Manager Praises Team Spirit After Tough Away Win",
        "content": "The head coach highlighted the squad's resilience following a hard-fought victory on the road.",
        "tag_name": "LaLiga",
        "image": "story6.jpg",
    },
    {
        "title": "Young Talent Impresses in Debut Season",
        "content": "A breakout academy graduate has caught the attention of scouts with his recent performances.",
        "tag_name": "Bundesliga",
        "image": "story7.jpg",
    },
    {
        "title": "Rivalry Renewed: Classic Clash Set for Sunday",
        "content": "Two historic rivals will face off in what promises to be a thrilling weekend fixture.",
        "tag_name": "Ligue 1",
        "image": "story8.jpg",
    },
    {
        "title": "Club Confirms New Signing Ahead of Season Opener",
        "content": "The team has completed the signing of a new player ahead of the upcoming campaign.",
        "tag_name": "Transfer",
        "image": "story9.jpg",
    },
    {
        "title": "Injury Update: Key Defender Ruled Out for Weeks",
        "content": "The club's medical team has confirmed a lengthy layoff for one of its first-team defenders.",
        "tag_name": "Premier League",
        "image": "story10.jpg",
    },
    {
        "title": "Breaking: New Signing Announced Ahead of Big Match",
        "content": "The club has confirmed a surprise new addition to the squad just days before their next important fixture.",
        "tag_name": "Premier League",
        "image": "story11.jpg",
    },
]
for i, item in enumerate(data, start=1):
    tag, _ = StoryTag.objects.get_or_create(name=item["tag_name"])
    story, created = Story.objects.get_or_create(
        title=item["title"],
        defaults={
            "content": f"<p>{item['content']}</p>",
            "summery": item["content"],
            "author": author,
            "status": "published",
            "post_type": "trending",
        },
    )
    if created:
        image_path = os.path.join("sample_images", item["image"])
        if os.path.exists(image_path):
            with open(image_path, "rb") as f:
                story.image.save(item["image"], File(f), save=True)

        story.tags.add(tag)

        StoryChapter.objects.get_or_create(
            story=story,
            order=1,
            defaults={
                "title": "Chapter 1",
                "slug": f"{story.slug}-chapter-1",
                "content": f"<p>{item['content']}</p>",
            },
        )

    print("Done:", item["title"])

print("Total trending:", Story.objects.filter(status="published", post_type="trending").count())