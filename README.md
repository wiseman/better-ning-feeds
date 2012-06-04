better-ning-feeds
=================

John Wiseman <jjwiseman@gmail.com>

Takes an existing Ning activity feed (RSS) and improves the feed by
adding more content in cases where Ning provides little or no content.

better-ning-feeds currently improves the following types of posts:

* Blog comments
* Forum replies

See below for details.


Blog comments
-------------

Comments on blog posts show up in the standard Ning activity feed like this:

<blockquote>
<p>
<a
href="http://diydrones.com/profile/EllisonChan?xg_source=activity">Ellison
Chan</a> <a
href="http://diydrones.com/xn/detail/705844:Comment:881177?xg_source=activity">replied</a>
to <a
href="http://diydrones.com/profile/EllisonChan?xg_source=activity">Ellison
Chan's</a> discussion <a
href="http://diydrones.com/xn/detail/705844:Topic:871958?xg_source=activity">Brainstorming
Specifications.</a> in the group <a
href="http://diydrones.com/xn/detail/705844:Group:871797?xg_source=activity">DIYDrones
- CNC Project</a>
</p>
</blockquote>

better-ning feeds show blog comments like this:

<blockquote>
<p>
<a
href="http://diydrones.com/profile/EllisonChan?xg_source=activity">Ellison
Chan</a> <a
href="http://diydrones.com/xn/detail/705844:Comment:881266?xg_source=activity">replied</a>
to <a
href="http://diydrones.com/profile/EllisonChan?xg_source=activity">Ellison
Chan's</a> discussion <a
href="http://diydrones.com/xn/detail/705844:Topic:871958?xg_source=activity">Brainstorming
Specifications.</a> in the group <a
href="http://diydrones.com/xn/detail/705844:Group:871797?xg_source=activity">DIYDrones
- CNC Project</a>
</p>
<p>
Monroe, yes the ESCs use back EMF to adjust the pole timings.  But
since we're using DC servo motors, it's simpler, and we're driving at
a higher level.  So it's more closer to how the AC sends pwm
signalling to the ESCs to turn the motors at a certain speed.  So
instead of reading the gyros, and acceleromters etc., we're reading
the encoders to tell us exactly where our motors are, and how fast to
drive them to get to the destination point.
</p>
<p>
The ArduCNC library is in my head. ;-) My imagination is vivid.</p>
</p>
</blockquote>


Forum replies
-------------

Discussion forum replies show up in the standard Ning feed like this:

<blockquote>
<a href="http://diydrones.com/profile/DeanWynton?xg_source=activity">Dean Wynton</a> <a href="http://diydrones.com/xn/detail/705844:Comment:881184?xg_source=activity">replied</a> to <a href="http://diydrones.com/profile/DeanWynton?xg_source=activity">Dean Wynton's</a> discussion <a href="http://diydrones.com/xn/detail/705844:Topic:840731?xg_source=activity">Tricopter APM2.0</a>
</blockquote>

better-ning-feeds expands them into this:

<blockquote>
<a href="http://diydrones.com/profile/DeanWynton?xg_source=activity">Dean Wynton</a> <a href="http://diydrones.com/xn/detail/705844:Comment:881263?xg_source=activity">replied</a> to <a href="http://diydrones.com/profile/DeanWynton?xg_source=activity">Dean Wynton's</a> discussion <a href="http://diydrones.com/xn/detail/705844:Topic:840731?xg_source=activity">Tricopter APM2.0</a><br>
<p>That is right Luke.. Its under the mission planner radio config, or it can be changed via the parameters list.</p>
</blockquote>
