# Trip 4

Hello, welcome to trip 4. I took a two week summer trip to japan with one day in south korea. What adventures will occur this time?

```
table of contents
```

<figure>
	<a id="random-pic-link"><img id="random-pic"></a>
	<figcaption>Here is a random picture. you can click on it to go to it in the story.</figcaption>
</figure>


```
inject photo list
```

<script>
const photo = photo_list[Math.floor(photo_list.length * Math.random())]

console.log(photo)

const [url, pic_url] = photo

document.querySelector("#random-pic").src = pic_url
document.querySelector("#random-pic-link").href = url

</script>

yeehaw