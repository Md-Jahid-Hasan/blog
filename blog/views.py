from django.shortcuts import render, get_object_or_404
from .models import Post, Comment
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .forms import EmailPostForm, CommentForm, SearchForm
from django.core.mail import send_mail
from taggit.models import Tag
from django.db.models import Count
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank, \
    TrigramSimilarity
##### For class Base View ######
from django.views.generic import ListView


class PostListView(ListView):
    queryset = Post.published.all()
    context_object_name = 'posts'
    paginate_by = 3
    template_name = 'blog/list.html'


def post_list(request, tag_slug=None):
    object_list = Post.published.all()
    tag = None
    if tag_slug:
        tag = get_object_or_404(Tag, slug=tag_slug)
        object_list = object_list.filter(tags__in=[tag])

    paginator = Paginator(object_list, 3)
    page = request.GET.get('page')
    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        posts = paginator.page(1)
    except EmptyPage:
        posts = paginator.page(paginator.num_pages)
    context = {
        'posts': posts,
        'page': page,
        'tag': tag,
    }
    return render(request, 'blog/list.html', context)


def post_details(request, year, month, day, post):
    post = get_object_or_404(Post, slug=post,
                             status='published',
                             publish__year=year,
                             publish__month=month,
                             publish__day=day)
    comments = post.comments.filter(active=True)
    new_comment = None
    if request.method == "POST":
        comment_form = CommentForm(data=request.POST)
        if comment_form.is_valid():
            new_comment = comment_form.save(commit=False)
            new_comment.post = post
            new_comment.save()
    else:
        comment_form = CommentForm()

    post_tags_id = post.tags.values_list('id', flat=True)

    similar_post = Post.published.filter(tags__in=post_tags_id).exclude(id=post.id)
    similar_post = similar_post.annotate(same=Count('tags')).order_by('-same','-publish')[:4]

    context = {
        'post': post,
        'comments': comments,
        'new_comment': new_comment,
        'comment_form': comment_form,
        'similar_posts': similar_post
    }
    return render(request, 'blog/detail.html', context)


def post_share(request, post_id):
    post = get_object_or_404(Post, id=post_id, status='published')
    sent = False
    if request.method == 'POST':
        form = EmailPostForm(request.POST)
        if form.is_valid():
            clear_data = form.cleaned_data
            post_url = request.build_absolute_uri(post.get_absolute_url())
            print(post_url)
            subject = f"{clear_data['name']} recommends you read {post.title}"
            message = f"Read {post.title} at {post_url}\n\n" \
                      f"{clear_data['name']}\'s comments: {clear_data['comments']}"
            send_mail(subject, message, 'admin@myblog.com', [clear_data['to']])
            sent = True

    else:
        form = EmailPostForm()
    context = {
        'post': post,
        'form': form,
        'sent': sent
    }
    return render(request, 'blog/post_share.html', context)


def post_search(request):
    form = SearchForm()
    query = None
    result = []
    
    if 'query' in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data['query']
            search_vector = SearchVector('title', weight='A') + \
                SearchVector('body', weight='B')
            search_query = SearchQuery(query)
            # result = Post.published.annotate(search=search_vector,
            #                                  rank=SearchRank(search_vector, search_query)
            #                                  ).filter(search=search_query).order_by('-rank')

            # result = Post.published.annotate(rank=SearchRank(search_vector, search_query)
            #                                  ).filter(rank__gte=0.3).order_by('-rank')

            result = Post.published.annotate(similarity=TrigramSimilarity('title', query),) \
                .filter(similarity__gt=0.1).order_by('-similarity')
    context = {
        'form': form,
        'query': query,
        'results': result,
    }
    return render(request, 'blog/search.html', context)
