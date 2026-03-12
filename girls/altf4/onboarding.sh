#!/usr/bin/env bash

curl -X POST 'http://127.0.0.1:8000/api/v1/influencers/onboarding' \
-F 'influencer_id=altf4girl' \
-F 'name=Alt Girl Dance' \
-F 'description=Alt-style dance creator focused on short-form dancing
content, expressive movement, confident camera presence, dark feminine
styling, and clean solo performance visuals.' \
-F 'hashtags=altgirl,dance,dancing,dancecreator,choreography,dancetrend,dancechal
lenge,solodance,altstyle,edgyfashion' \
-F 'video_suggestions_requirement=Do not use blurred footage, crowded
scenes, heavy occlusion, multi-person choreography without a clear main
subject, extreme low light, aggressive camera shake, unrelated themes, or
clips where the face is hidden.' \
-F 'reference_image=@/root/workspace/altf4girl.png'