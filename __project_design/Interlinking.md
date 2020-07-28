# Types of interlinking in Recipe Blog posts

## External Link
- URI is to a another website.
- Standard Markdown
	- `[Link text](https://uri.com/foodbar)`
---
## Internal Link
- Linking to a recipe or another post on the same blog
- Roam/Wiki type double bracket link
	- `[[Title of thing]]`
	- Cons:
		- literal string comparison, prone to errors
		- Can't use alternate link text as the Title is the ID used to link
---
## Transclusion
Including content from another page/data source in the post / on the post page via some shorthand code in post.

_Not fully figured out yet though some code is present._

### Recipe Data
In the case of Recipes, ability to pick:
- Ingredients, 
- Directions, 
- Description,
- any of the metadata,
- predefined metadata blocks

*Proof of concept code exists but haven;'t integrated shorthand for embedding in blog post yet.*

### Other posts/notes
#### In the body of the post
*Not figured out yet.*

#### Mentioned in body of post but shown in sidebar ("sidenote" or "marginnote")
Code exists in the `content.html` include
Currently: `[[Title: rsn-transclude]]`

---
## Linked Mentions
"_Posts that link to this one_"
- Can be added to the foot of the page via templates
- Title and excerpt (transclusion) of any post linking to this one
---
## Unlinked Mentions
"_What mentions this post without linking to it_"
- Can be added to the foot of the page via templates
- Title and excerpt (transclusion) of any post linking to this one
