"""Blog listing and blog detail pages."""
from django import forms
from django.db import models
from django.shortcuts import render
from taggit.models import TaggedItemBase
from modelcluster.contrib.taggit import ClusterTaggableManager
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from wagtail.admin.edit_handlers import (
    FieldPanel,
    StreamFieldPanel,
    MultiFieldPanel,
    InlinePanel,
)

from wagtail.images.api.fields import ImageRenditionField

from wagtail.api import APIField
from rest_framework.fields import Field
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from wagtail.snippets.edit_handlers import SnippetChooserPanel
from wagtail.core.fields import StreamField
from wagtail.core.models import Page, Orderable
from wagtail.images.edit_handlers import ImageChooserPanel
from wagtail.contrib.routable_page.models import RoutablePageMixin, route
from wagtail.snippets.models import register_snippet
from streams import blocks


class ImageSerializedField(Field):
    """A custom serializer used in Wagtails v2 API."""

    def to_representation(self, value):
        """Return the image URL, title and dimensions."""
        return {
            "url": value.file.url,
            "title": value.title,
            "width": value.width,
            "height": value.height,
        }
class BlogAuthorsOrderable(Orderable):
    """This allows us to select one or more blog authors from Snippets."""

    page = ParentalKey("blog.BlogDetailPage", related_name="blog_authors")
    author = models.ForeignKey(
        "blog.BlogAuthor",
        on_delete=models.CASCADE,
    )
    panels = [
        SnippetChooserPanel("author"),
    ]
    @property
    def author_name(self):
        return self.author.name
    @property
    def author_website(self):
        return self.author.website

    @property
    def author_image(self):
        return self.author.image

    api_fields = [
        APIField("author_name"),
        APIField("author_website"),
        APIField("author_image", serializer=ImageSerializedField()),
       # The below APIField is using a Wagtail-built DRF Serializer that supports
        # custom image rendition sizes
        APIField(
            "image",
            serializer=ImageRenditionField(
                'fill-200x250',
                source="author_image"
            )
        ),
    
    
    ]

class BlogAuthor(models.Model):
    """Blog author for snippets."""
    name = models.CharField(max_length=100)
    website = models.URLField(blank=True, null=True)
    image = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
        related_name="+",
    )
    panels = [
        MultiFieldPanel(
            [
                FieldPanel("name"),
                ImageChooserPanel("image"),
            ],
            heading="Name and Image",
        ),
        MultiFieldPanel(
            [
                FieldPanel("website"),
            ],
            heading="Links"
        )
    ]
    def __str__(self):
        """String repr of this class."""
        return self.name
    class Meta:  # noqa
        verbose_name = "Blog Author"
        verbose_name_plural = "Blog Authors"
register_snippet(BlogAuthor)
class BlogCategory(models.Model):
    """Blog catgory for a snippet."""
    name = models.CharField(max_length=255)
    slug = models.SlugField(
        verbose_name="slug",
        allow_unicode=True,
        max_length=255,
        help_text='A slug to identify posts by this category',
    )
    panels = [
        FieldPanel("name"),
        FieldPanel("slug"),
    ]
    class Meta:
        verbose_name = "Blog Category"
        verbose_name_plural = "Blog Categories"
        ordering = ["name"]
    def __str__(self):
        return self.name
register_snippet(BlogCategory)
class BlogListingPage(RoutablePageMixin, Page):




    """Listing page lists all the Blog Detail Pages."""



    template = "blog/blog_listing_page.html"
    ajax_template = "blog/blog_listing_page_ajax.html"
    max_count = 1
    subpage_types = ['blog.VideoBlogPage', 'blog.ArticleBlogPage']
    custom_title = models.CharField(
        max_length=100,
        blank=False,
        null=False,
        help_text='Overwrites the default title',
    )
    content_panels = Page.content_panels + [
        FieldPanel("custom_title"),
    ]
    def get_context(self, request, *args, **kwargs):
        """Adding custom stuff to our context."""
        context = super().get_context(request, *args, **kwargs)
          # Get all posts
        all_posts = BlogDetailPage.objects.live().public().order_by('-first_published_at')
        # Paginate all posts by 2 per page
        if request.GET.get('tag', None):
            tags = request.GET.get('tag')
            all_posts = all_posts.filter(tags__slug__in=[tags]) 





        paginator = Paginator(all_posts, 2)
        # Try to get the ?page=x value
        page = request.GET.get("page")
        try:
            # If the page exists and the ?page=x is an int
            posts = paginator.page(page)
        except PageNotAnInteger:
            # If the ?page=x is not an int; show the first page
            posts = paginator.page(1)
        except EmptyPage:
            # If the ?page=x is out of range (too high most likely)
            # Then return the last page
            posts = paginator.page(paginator.num_pages)







        context["posts"] = posts
        context["categories"] = BlogCategory.objects.all()
        return context







    @route(r'^latest/$', name="latest_posts")


    
    def latest_blog_posts_only_shows_last_5(self, request, *args, **kwargs):
        context = self.get_context(request, *args, **kwargs)
        context["posts"] = context["posts"][:1]
        return render(request, "blog/latest_posts.html", context)





    def get_sitemap_urls(self, request):
        # Uncomment to have no sitemap for this page
        # return []
        sitemap = super().get_sitemap_urls(request)
        sitemap.append(
            {
                "location": self.full_url + self.reverse_subpage("latest_posts"),
                "lastmod": (self.last_published_at or self.latest_revision_created_at),
                "priority": 0.9,
            }
        )
        return sitemap

    


class BlogPageTag(TaggedItemBase):
    content_object = ParentalKey(
        'BlogDetailPage',
        related_name='tagged_items',
        on_delete=models.CASCADE,
    )










class BlogDetailPage(Page):
    """Parental blog detail page."""
    subpage_types = []
    parent_page_types = ['blog.BlogListingPage']


    tags = ClusterTaggableManager(through=BlogPageTag, blank=True)

    custom_title = models.CharField(
        max_length=100,
        blank=False,
        null=False,
        help_text='Overwrites the default title',
    )
    banner_image = models.ForeignKey(
        "wagtailimages.Image",
        blank=False,
        null=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )


    categories = ParentalManyToManyField("blog.BlogCategory", blank=True)
    content = StreamField(
        [
            ("title_and_text", blocks.TitleAndTextBlock()),
            ("full_richtext", blocks.RichtextBlock()),
            ("simple_richtext", blocks.SimpleRichtextBlock()),
            ("cards", blocks.CardBlock()),
            ("cta", blocks.CTABlock()),
        ],
        null=True,
        blank=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("custom_title"),
        FieldPanel("tags"),
        ImageChooserPanel("banner_image"),
        MultiFieldPanel(
            [
                InlinePanel("blog_authors", label="Author", min_num=1, max_num=4)
            ],
            heading="Author(s)"
        ),
        MultiFieldPanel(
            [
                FieldPanel("categories", widget=forms.CheckboxSelectMultiple)
            ],
            heading="Categories"
        ),
        StreamFieldPanel("content"),
    ]


# First subclassed blog post page
class ArticleBlogPage(BlogDetailPage):
    """A subclassed blog post page for articles."""

    template = "blog/article_blog_page.html"

    subtitle = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    intro_image = models.ForeignKey(
        "wagtailimages.Image",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        help_text='Best size for this image will be 1400x400'
    )

    content_panels = Page.content_panels + [
        FieldPanel("custom_title"),
        FieldPanel("tags"),

        FieldPanel("subtitle"),
        ImageChooserPanel("banner_image"),
        ImageChooserPanel("intro_image"),
        MultiFieldPanel(
            [
                InlinePanel("blog_authors", label="Author", min_num=1, max_num=4)
            ],
            heading="Author(s)"
        ),
        MultiFieldPanel(
            [
                FieldPanel("categories", widget=forms.CheckboxSelectMultiple)
            ],
            heading="Categories"
        ),
        StreamFieldPanel("content"),
    ]


# Second subclassed page
class VideoBlogPage(BlogDetailPage):

    """A video subclassed page."""

    template = "blog/video_blog_page.html"

    youtube_video_id = models.CharField(max_length=30)

    content_panels = Page.content_panels + [
        FieldPanel("custom_title"),
        FieldPanel("tags"),
        ImageChooserPanel("banner_image"),
        MultiFieldPanel(
            [
                InlinePanel("blog_authors", label="Author", min_num=1, max_num=4)
            ],
            heading="Author(s)"
        ),
        MultiFieldPanel(
            [
                FieldPanel("categories", widget=forms.CheckboxSelectMultiple)
            ],
            heading="Categories"
        ),
        FieldPanel("youtube_video_id"),
        StreamFieldPanel("content"),
    ]


def save(self, *args, **kwargs):
        """Create a template fragment key.
        Then delete the key."""
        key = make_template_fragment_key(
            "blog_post_preview",
            [self.id]
        )
        cache.delete(key)
        return super().save(*args, **kwargs)     

